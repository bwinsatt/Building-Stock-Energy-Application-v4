#!/usr/bin/env python3
"""
Prediction pipeline for per-fuel-type upgrade models.

Loads one model per fuel type for a given upgrade, predicts EUI by fuel,
and sums for total. Ensures parts always equal the whole.

Usage as module:
    from scripts.predict import UpgradePredictor

    predictor = UpgradePredictor('ComStock', upgrade_id=0)
    result = predictor.predict({
        'in.comstock_building_type_group': 'Office',
        'in.sqft..ft2': 50000,
        'in.number_stories': '3',
        ...
    })
    print(result)
    # {
    #   'eui_by_fuel_kbtu_sf': {'electricity': 45.2, 'natural_gas': 38.1, ...},
    #   'total_eui_kbtu_sf': 83.3
    # }

Usage as CLI:
    python3 scripts/predict.py --dataset ComStock --upgrade 0 --input input.csv --output predictions.csv
"""
import os
import sys
import json
import argparse
import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.training_utils import encode_features

MODEL_DIRS = {
    'ComStock': os.path.join(PROJECT_ROOT, 'XGB_Models', 'ComStock_Upgrades_2025_R3'),
    'ResStock': os.path.join(PROJECT_ROOT, 'XGB_Models', 'ResStock_Upgrades_2025_R1'),
}

DATASET_FUEL_TYPES = {
    'ComStock': ['electricity', 'natural_gas', 'fuel_oil', 'propane', 'district_heating'],
    'ResStock': ['electricity', 'natural_gas', 'fuel_oil', 'propane'],
}


class UpgradePredictor:
    """Load per-fuel-type models for an upgrade and predict EUI by fuel."""

    def __init__(self, dataset, upgrade_id, model_dir=None):
        """
        Args:
            dataset: 'ComStock' or 'ResStock'
            upgrade_id: integer upgrade ID (0 = baseline)
            model_dir: override model directory (default: auto from dataset)
        """
        if model_dir is None:
            model_dir = MODEL_DIRS[dataset]

        self.dataset = dataset
        self.upgrade_id = upgrade_id
        self.fuel_types = DATASET_FUEL_TYPES[dataset]
        self.models = {}
        self.encoders = None
        self.feature_cols = None
        self.metrics = {}

        for fuel in self.fuel_types:
            model_name = f'XGB_upgrade{upgrade_id}_{fuel}'
            model_path = os.path.join(model_dir, f'{model_name}.pkl')
            enc_path = os.path.join(model_dir, f'{model_name}_encoders.pkl')
            meta_path = os.path.join(model_dir, f'{model_name}_meta.json')

            if not os.path.exists(model_path):
                raise FileNotFoundError(
                    f"Model not found: {model_path}\n"
                    f"Train it first with: python3 scripts/train_{dataset.lower()}_upgrades.py "
                    f"--upgrades {upgrade_id} --skip-tuning"
                )

            self.models[fuel] = joblib.load(model_path)
            with open(meta_path) as f:
                meta = json.load(f)
            self.metrics[fuel] = meta['metrics']

            # Encoders and feature_cols are the same across fuel types for a given upgrade
            if self.encoders is None:
                self.encoders = joblib.load(enc_path)
                self.feature_cols = meta['feature_columns']

    def predict(self, input_data):
        """
        Predict EUI by fuel type for one or more buildings.

        Args:
            input_data: dict (single building) or DataFrame (multiple buildings)
                        Keys/columns must match feature_columns from training.

        Returns:
            Single building: dict with 'eui_by_fuel_kbtu_sf' and 'total_eui_kbtu_sf'
            Multiple buildings: DataFrame with per-fuel and total EUI columns
        """
        if isinstance(input_data, dict):
            df = pd.DataFrame([input_data])
            single = True
        else:
            df = input_data.copy()
            single = False

        # Validate required features
        missing = [c for c in self.feature_cols if c not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required features: {missing}\n"
                f"Required: {self.feature_cols}"
            )

        # Encode once (shared across fuel types)
        X_enc, _ = encode_features(df, self.feature_cols, encoders=self.encoders)

        # Predict each fuel type
        fuel_preds_kwh = {}
        for fuel in self.fuel_types:
            y_pred = self.models[fuel].predict(X_enc)
            # Clamp negative predictions to 0 (EUI can't be negative)
            y_pred = np.maximum(y_pred, 0)
            fuel_preds_kwh[fuel] = y_pred

        if single:
            eui_by_fuel = {fuel: float(preds[0]) * 3.412
                           for fuel, preds in fuel_preds_kwh.items()}
            total = sum(eui_by_fuel.values())
            return {
                'eui_by_fuel_kwh_ft2': {fuel: float(preds[0])
                                         for fuel, preds in fuel_preds_kwh.items()},
                'eui_by_fuel_kbtu_sf': eui_by_fuel,
                'total_eui_kwh_ft2': sum(float(preds[0]) for preds in fuel_preds_kwh.values()),
                'total_eui_kbtu_sf': total,
            }
        else:
            result = df.copy()
            total_kwh = np.zeros(len(df))
            for fuel, preds in fuel_preds_kwh.items():
                result[f'predicted_{fuel}_eui_kwh_ft2'] = preds
                result[f'predicted_{fuel}_eui_kbtu_sf'] = preds * 3.412
                total_kwh += preds
            result['predicted_total_eui_kwh_ft2'] = total_kwh
            result['predicted_total_eui_kbtu_sf'] = total_kwh * 3.412
            return result

    def predict_savings(self, input_data, baseline_predictor):
        """
        Predict savings vs baseline for one or more buildings.

        Args:
            input_data: dict or DataFrame
            baseline_predictor: UpgradePredictor for upgrade 0

        Returns:
            Single: dict with savings by fuel type and total
            Multiple: DataFrame with savings columns
        """
        baseline = baseline_predictor.predict(input_data)
        upgrade = self.predict(input_data)

        if isinstance(input_data, dict):
            savings_by_fuel = {}
            for fuel in self.fuel_types:
                base_val = baseline['eui_by_fuel_kbtu_sf'][fuel]
                upgr_val = upgrade['eui_by_fuel_kbtu_sf'][fuel]
                savings_by_fuel[fuel] = base_val - upgr_val

            total_savings = sum(savings_by_fuel.values())
            savings_pct = (total_savings / baseline['total_eui_kbtu_sf'] * 100
                           if baseline['total_eui_kbtu_sf'] > 0 else 0)

            return {
                'baseline': baseline,
                'post_upgrade': upgrade,
                'savings_by_fuel_kbtu_sf': savings_by_fuel,
                'total_savings_kbtu_sf': total_savings,
                'savings_pct': savings_pct,
            }
        else:
            result = upgrade.copy()
            total_savings_kwh = np.zeros(len(result))
            for fuel in self.fuel_types:
                base_col = baseline[f'predicted_{fuel}_eui_kbtu_sf']
                upgr_col = result[f'predicted_{fuel}_eui_kbtu_sf']
                result[f'savings_{fuel}_kbtu_sf'] = base_col - upgr_col
                total_savings_kwh += (baseline[f'predicted_{fuel}_eui_kwh_ft2']
                                      - result[f'predicted_{fuel}_eui_kwh_ft2'])
            result['total_savings_kbtu_sf'] = total_savings_kwh * 3.412
            result['baseline_total_eui_kbtu_sf'] = baseline['predicted_total_eui_kbtu_sf']
            result['savings_pct'] = np.where(
                result['baseline_total_eui_kbtu_sf'] > 0,
                result['total_savings_kbtu_sf'] / result['baseline_total_eui_kbtu_sf'] * 100,
                0
            )
            return result

    def get_feature_info(self):
        """Return feature columns and their expected categories."""
        info = {}
        for col in self.feature_cols:
            if col in self.encoders:
                enc = self.encoders[col]
                if isinstance(enc, list):
                    info[col] = {'type': 'categorical', 'categories': enc}
                else:
                    info[col] = {'type': 'categorical', 'categories': list(enc.classes_)}
            else:
                info[col] = {'type': 'numeric'}
        return info

    def __repr__(self):
        fuel_r2 = {f: self.metrics[f].get('r2', 0) for f in self.fuel_types}
        avg_r2 = sum(fuel_r2.values()) / len(fuel_r2)
        return (f"UpgradePredictor(dataset='{self.dataset}', upgrade_id={self.upgrade_id}, "
                f"fuels={len(self.fuel_types)}, features={len(self.feature_cols)}, "
                f"avg_r2={avg_r2:.4f})")


def list_available_models(dataset):
    """List all trained upgrades for a dataset (grouped by upgrade, not fuel)."""
    model_dir = MODEL_DIRS[dataset]
    if not os.path.exists(model_dir):
        return []

    fuel_types = DATASET_FUEL_TYPES[dataset]
    # Find unique upgrade IDs from electricity models (always present)
    upgrades = {}
    for f in sorted(os.listdir(model_dir)):
        if f.endswith('_meta.json') and '_electricity_' in f:
            uid_str = f.replace('XGB_upgrade', '').replace('_electricity_meta.json', '')
            try:
                uid = int(uid_str)
            except ValueError:
                continue
            with open(os.path.join(model_dir, f)) as fh:
                meta = json.load(fh)
            upgrades[uid] = {
                'upgrade_id': uid,
                'electricity_r2': meta['metrics'].get('r2'),
                'electricity_mae_kbtu_sf': meta['metrics'].get('mae_kbtu_sf'),
                'n_samples': meta['metrics'].get('n_samples'),
            }
            # Load other fuel metrics
            for fuel in fuel_types[1:]:
                fuel_meta_path = os.path.join(model_dir, f'XGB_upgrade{uid}_{fuel}_meta.json')
                if os.path.exists(fuel_meta_path):
                    with open(fuel_meta_path) as fh:
                        fm = json.load(fh)
                    upgrades[uid][f'{fuel}_r2'] = fm['metrics'].get('r2')

    return [upgrades[k] for k in sorted(upgrades.keys())]


# ==============================================================================
# CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description='Predict EUI using trained upgrade models')
    parser.add_argument('--dataset', required=True, choices=['ComStock', 'ResStock'],
                        help='Which dataset models to use')
    parser.add_argument('--upgrade', required=True, type=int,
                        help='Upgrade ID (0 = baseline)')
    parser.add_argument('--input', required=True,
                        help='Input CSV with feature columns')
    parser.add_argument('--output', default=None,
                        help='Output CSV path (default: stdout)')
    parser.add_argument('--with-savings', action='store_true',
                        help='Include savings vs baseline (loads baseline model too)')
    parser.add_argument('--list-features', action='store_true',
                        help='Print required features and exit')
    parser.add_argument('--list-models', action='store_true',
                        help='List available models and exit')
    args = parser.parse_args()

    if args.list_models:
        models = list_available_models(args.dataset)
        fuel_types = DATASET_FUEL_TYPES[args.dataset]
        print(f"\n{args.dataset} upgrades ({len(models)} available, "
              f"{len(fuel_types)} fuel types each):\n")
        header = f"{'ID':>4}  {'Elec R²':>8}  {'Elec MAE':>9}  {'Samples':>8}"
        print(header)
        print("-" * len(header))
        for m in models:
            print(f"{m['upgrade_id']:>4}  {m['electricity_r2']:>8.4f}  "
                  f"{m['electricity_mae_kbtu_sf']:>9.2f}  {m['n_samples']:>8}")
        return

    predictor = UpgradePredictor(args.dataset, args.upgrade)

    if args.list_features:
        info = predictor.get_feature_info()
        print(f"\nRequired features for {args.dataset} upgrade {args.upgrade}:\n")
        for col, details in info.items():
            if details['type'] == 'categorical':
                cats = details['categories']
                print(f"  {col} (categorical, {len(cats)} values)")
                for c in cats[:5]:
                    print(f"    - {c}")
                if len(cats) > 5:
                    print(f"    ... and {len(cats) - 5} more")
            else:
                print(f"  {col} (numeric)")
        return

    # Load input and predict
    input_df = pd.read_csv(args.input)
    print(f"Loaded {len(input_df)} buildings from {args.input}")

    if args.with_savings and args.upgrade != 0:
        baseline = UpgradePredictor(args.dataset, 0)
        result = predictor.predict_savings(input_df, baseline)
    else:
        result = predictor.predict(input_df)

    if args.output:
        result.to_csv(args.output, index=False)
        print(f"Predictions saved to {args.output}")
    else:
        # Show summary of fuel-type predictions
        fuel_types = DATASET_FUEL_TYPES[args.dataset]
        cols = [f'predicted_{f}_eui_kbtu_sf' for f in fuel_types] + ['predicted_total_eui_kbtu_sf']
        if 'total_savings_kbtu_sf' in result.columns:
            cols += ['total_savings_kbtu_sf', 'savings_pct']
        print(result[cols].describe())


if __name__ == '__main__':
    main()
