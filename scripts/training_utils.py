"""
Shared utilities for training XGBoost upgrade models.
Used by train_comstock_upgrades.py and train_resstock_upgrades.py.
"""
import os
import json
import time
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False
    print("WARNING: optuna not installed. Using default hyperparameters.")


def load_upgrades_lookup(path):
    """Load upgrade ID -> name mapping."""
    with open(path) as f:
        return json.load(f)


def encode_features(df, feature_cols, encoders=None):
    """
    Convert string/categorical columns to pandas Categorical dtype for
    XGBoost's native categorical support. Numeric columns pass through.

    Args:
        df: DataFrame with feature columns
        feature_cols: list of column names to encode
        encoders: dict of {col_name: list of categories} from training.
                  If None, fit new categories from data.

    Returns:
        df_encoded: DataFrame with categorical features
        encoders: dict of {col_name: list of categories}
    """
    df_enc = df[feature_cols].copy()
    if encoders is None:
        encoders = {}
        fit = True
    else:
        fit = False

    for col in feature_cols:
        if df_enc[col].dtype == 'object' or str(df_enc[col].dtype) in ('large_string', 'string'):
            df_enc[col] = df_enc[col].astype(str)
            if fit:
                categories = sorted(df_enc[col].unique().tolist())
                encoders[col] = categories
                df_enc[col] = pd.Categorical(df_enc[col], categories=categories)
            else:
                if col in encoders:
                    enc = encoders[col]
                    # Support both formats: list of categories (new) or LabelEncoder (legacy)
                    if isinstance(enc, list):
                        categories = enc
                        known = set(categories)
                        df_enc[col] = df_enc[col].apply(lambda x: x if x in known else categories[0])
                        df_enc[col] = pd.Categorical(df_enc[col], categories=categories)
                    else:
                        # Legacy LabelEncoder from old models
                        known = set(enc.classes_)
                        df_enc[col] = df_enc[col].apply(lambda x: x if x in known else enc.classes_[0])
                        df_enc[col] = enc.transform(df_enc[col])
                else:
                    # Column was numeric during training
                    df_enc[col] = pd.to_numeric(df_enc[col], errors='coerce')
        else:
            df_enc[col] = pd.to_numeric(df_enc[col], errors='coerce')

    return df_enc, encoders


def tune_hyperparameters(X_train, y_train, n_trials=50, cv_folds=5, random_state=42):
    """
    Use Optuna to find optimal XGBoost hyperparameters.

    Returns:
        best_params: dict of best hyperparameters
    """
    if not HAS_OPTUNA:
        return {
            'n_estimators': 300,
            'max_depth': 6,
            'learning_rate': 0.1,
            'min_child_weight': 5,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
        }

    # Determine optimal thread allocation to avoid oversubscription.
    # cross_val_score parallelizes across CV folds, so give each XGBoost
    # worker a share of cores rather than all of them.
    import multiprocessing
    n_cpus = multiprocessing.cpu_count()
    xgb_threads = 1
    cv_workers = min(cv_folds, n_cpus)

    def objective(trial):
        params = {
            'n_estimators': trial.suggest_int('n_estimators', 100, 800),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-3, 10.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-3, 10.0, log=True),
        }
        model = XGBRegressor(
            objective='reg:squarederror',
            random_state=random_state,
            n_jobs=xgb_threads,
            enable_categorical=True,
            **params
        )
        scores = cross_val_score(
            model, X_train, y_train,
            cv=cv_folds,
            scoring='neg_mean_absolute_error',
            n_jobs=cv_workers
        )
        return -scores.mean()  # Optuna minimizes

    study = optuna.create_study(direction='minimize')
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    return study.best_params


def train_single_model(X_train, y_train, params, random_state=42):
    """Train a single XGBoost model with given parameters."""
    model = XGBRegressor(
        objective='reg:squarederror',
        random_state=random_state,
        n_jobs=-1,
        enable_categorical=True,
        **params
    )
    model.fit(X_train, y_train)
    return model


def prepare_catboost_data(df, feature_cols, cat_feature_names):
    """Prepare DataFrame for CatBoost: string-typed categoricals, numeric pass-through."""
    df_cb = df[feature_cols].copy()
    for col in feature_cols:
        if col in cat_feature_names:
            df_cb[col] = df_cb[col].astype(str)
        else:
            df_cb[col] = pd.to_numeric(df_cb[col], errors='coerce')
            # DO NOT fillna — CatBoost handles NaN natively
    return df_cb


def train_lightgbm_model(X_train, y_train, params, cat_indices, random_state=42):
    """Train a LightGBM model. X_train should have pd.Categorical dtype columns."""
    from lightgbm import LGBMRegressor
    lgbm_params = {
        'objective': 'regression',
        'n_estimators': params.get('n_estimators', 300),
        'max_depth': params.get('max_depth', 6),
        'learning_rate': params.get('learning_rate', 0.1),
        'min_child_weight': params.get('min_child_weight', 5),
        'subsample': params.get('subsample', 0.8),
        'colsample_bytree': params.get('colsample_bytree', 0.8),
        'random_state': random_state,
        'n_jobs': -1,
        'verbose': -1,
    }
    model = LGBMRegressor(**lgbm_params)
    model.fit(X_train, y_train, categorical_feature=cat_indices)
    return model


def train_catboost_model(X_train_str, y_train, params, cat_indices, random_state=42):
    """Train a CatBoost model. X_train_str must have string-typed categoricals."""
    from catboost import CatBoostRegressor
    model = CatBoostRegressor(
        iterations=params.get('n_estimators', 300),
        depth=min(params.get('max_depth', 6), 10),
        learning_rate=params.get('learning_rate', 0.1),
        random_seed=random_state,
        verbose=0,
        cat_features=cat_indices,
    )
    model.fit(X_train_str, y_train)
    return model


def evaluate_model(model, X_test, y_test, convert_kbtu=True, log_target=False):
    """
    Evaluate model on test set.

    If log_target=True, y_test is in log1p space and predictions are
    inverse-transformed before computing metrics in original units.

    Returns dict with MAE, RMSE, R², and MAE in kBtu/sf if convert_kbtu=True.
    """
    y_pred = model.predict(X_test)
    if log_target:
        y_pred_orig = np.expm1(y_pred)
        y_test_orig = np.expm1(y_test)
    else:
        y_pred_orig = y_pred
        y_test_orig = y_test
    metrics = {
        'mae_kwh_ft2': mean_absolute_error(y_test_orig, y_pred_orig),
        'rmse_kwh_ft2': np.sqrt(mean_squared_error(y_test_orig, y_pred_orig)),
        'r2': r2_score(y_test_orig, y_pred_orig),
        'n_samples': len(y_test),
    }
    if convert_kbtu:
        metrics['mae_kbtu_sf'] = metrics['mae_kwh_ft2'] * 3.412
    return metrics


def save_model_artifacts(model, encoders, feature_cols, metrics, output_dir, model_name,
                         log_target=False):
    """
    Save model, encoders, and metadata to disk.

    Saves:
      - {model_name}.pkl (the XGBoost model)
      - {model_name}_encoders.pkl (category mappings for inference)
      - {model_name}_meta.json (feature list, metrics, training info)
    """
    os.makedirs(output_dir, exist_ok=True)

    # Save model
    model_path = os.path.join(output_dir, f'{model_name}.pkl')
    joblib.dump(model, model_path)

    # Save encoders (category lists per column)
    enc_path = os.path.join(output_dir, f'{model_name}_encoders.pkl')
    joblib.dump(encoders, enc_path)

    # Save metadata
    meta = {
        'feature_columns': feature_cols,
        'metrics': metrics,
        'model_file': f'{model_name}.pkl',
        'encoder_file': f'{model_name}_encoders.pkl',
        'log_target': log_target,
    }
    meta_path = os.path.join(output_dir, f'{model_name}_meta.json')
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    return model_path
