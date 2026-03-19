#!/usr/bin/env python3
"""
One-time script: enrich zipcode_lookup.json with HDD/CDD and save cluster_hdd_cdd.json.

Extracts cluster-level median HDD65F and CDD65F from ComStock out.params,
then merges into each zipcode prefix entry via its cluster_name.
Also saves a standalone cluster_hdd_cdd.json for training scripts (ResStock needs this).

Usage:
    python3 scripts/build_hdd_cdd_lookup.py
    python3 scripts/build_hdd_cdd_lookup.py --dry-run  # preview without writing
"""
import os
import json
import argparse
import pandas as pd

# The script lives in scripts/ inside the worktree.
# ComStock data is NOT in the worktree — it lives in the main repo root.
# Worktrees are nested under .claude/worktrees/<name>/ inside the main repo,
# so we walk up to find the directory that contains the ComStock folder.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Worktree root (contains scripts/, backend/, etc.)
PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)


def find_comstock_root():
    """
    Return the directory that contains the 'ComStock' subdirectory.

    Check PROJECT_ROOT first (normal case), then walk up the directory tree
    to handle worktrees nested inside .claude/worktrees/<name>/.
    """
    candidate = PROJECT_ROOT
    for _ in range(6):  # walk up at most 6 levels
        if os.path.isdir(os.path.join(candidate, 'ComStock')):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    raise FileNotFoundError(
        "Could not find a 'ComStock' directory at or above: "
        f"{PROJECT_ROOT}\n"
        "Make sure you are running this script from within the project tree."
    )


def build_cluster_hdd_cdd(comstock_root):
    """Extract cluster -> median HDD/CDD from ComStock baseline data."""
    raw_dir = os.path.join(comstock_root, 'ComStock', 'raw_data')
    lookup_path = os.path.join(comstock_root, 'ComStock', 'spatial_tract_lookup_table.csv')

    parquet_path = os.path.join(raw_dir, 'upgrade0_agg.parquet')
    print(f"  Loading parquet: {parquet_path}")

    # Load baseline buildings with HDD/CDD
    df = pd.read_parquet(
        parquet_path,
        columns=['bldg_id', 'in.as_simulated_nhgis_county_gisjoin',
                 'out.params.hdd65f', 'out.params.cdd65f']
    )
    df = df.drop_duplicates(subset='bldg_id')
    print(f"  Loaded {len(df):,} unique buildings")

    # Join cluster_name
    print(f"  Loading spatial lookup: {lookup_path}")
    cluster = pd.read_csv(lookup_path,
                          usecols=['nhgis_county_gisjoin', 'cluster_name'],
                          low_memory=False)
    cluster = cluster.drop_duplicates(subset='nhgis_county_gisjoin')
    df = df.merge(cluster,
                  left_on='in.as_simulated_nhgis_county_gisjoin',
                  right_on='nhgis_county_gisjoin', how='left')

    unjoined = df['cluster_name'].isna().sum()
    if unjoined:
        print(f"  Warning: {unjoined:,} buildings had no cluster match (will be excluded from aggregation)")

    # Aggregate by cluster (median is robust to outliers)
    result = df.groupby('cluster_name').agg(
        hdd65f=('out.params.hdd65f', 'median'),
        cdd65f=('out.params.cdd65f', 'median'),
    ).round(1)

    return result.to_dict('index')


def save_cluster_hdd_cdd(cluster_hdd_cdd, dry_run=False):
    """Save standalone cluster -> HDD/CDD JSON for training scripts."""
    out_path = os.path.join(
        PROJECT_ROOT, 'backend', 'app', 'data', 'cluster_hdd_cdd.json'
    )
    if not dry_run:
        with open(out_path, 'w') as f:
            json.dump(cluster_hdd_cdd, f, indent=2)
        print(f"  Saved cluster_hdd_cdd.json ({len(cluster_hdd_cdd)} clusters) to {out_path}")
    else:
        print(f"  DRY RUN — would save {len(cluster_hdd_cdd)} clusters to {out_path}")
        # Show a sample cluster
        sample_cluster = list(cluster_hdd_cdd.keys())[0]
        print(f"  Sample cluster '{sample_cluster}': {cluster_hdd_cdd[sample_cluster]}")


def enrich_zipcode_lookup(cluster_hdd_cdd, dry_run=False):
    """Add hdd65f and cdd65f to each prefix entry in zipcode_lookup.json."""
    lookup_path = os.path.join(
        PROJECT_ROOT, 'backend', 'app', 'data', 'zipcode_lookup.json'
    )
    with open(lookup_path) as f:
        data = json.load(f)

    prefixes = data['prefixes']
    matched = 0
    unmatched = 0
    unmatched_clusters = set()

    for prefix, entry in prefixes.items():
        cluster = entry.get('cluster_name')
        if cluster and cluster in cluster_hdd_cdd:
            entry['hdd65f'] = cluster_hdd_cdd[cluster]['hdd65f']
            entry['cdd65f'] = cluster_hdd_cdd[cluster]['cdd65f']
            matched += 1
        else:
            # Fallback: use national median
            entry['hdd65f'] = 4800.0
            entry['cdd65f'] = 1400.0
            unmatched += 1
            if cluster:
                unmatched_clusters.add(cluster)

    # Also enrich state_defaults if they exist
    if 'state_defaults' in data:
        for state, entry in data['state_defaults'].items():
            cluster = entry.get('cluster_name')
            if cluster and cluster in cluster_hdd_cdd:
                entry['hdd65f'] = cluster_hdd_cdd[cluster]['hdd65f']
                entry['cdd65f'] = cluster_hdd_cdd[cluster]['cdd65f']

    print(f"  Enriched {matched} prefixes with cluster-level HDD/CDD")
    if unmatched:
        print(f"  {unmatched} prefixes used national median fallback")
        if unmatched_clusters:
            print(f"  Unmatched clusters: {unmatched_clusters}")

    if not dry_run:
        with open(lookup_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  Written to {lookup_path}")
    else:
        print("  DRY RUN — no files written")
        # Show a sample prefix
        sample_prefix = list(prefixes.keys())[0]
        print(f"  Sample entry '{sample_prefix}': {json.dumps(prefixes[sample_prefix], indent=4)}")

    # Always print the NYC prefix (100) for verification
    if '100' in prefixes:
        nyc = prefixes['100']
        print(f"\n  NYC prefix '100' check:")
        print(f"    cluster_name: {nyc.get('cluster_name')}")
        print(f"    hdd65f: {nyc.get('hdd65f')} (expect ~4964)")
        print(f"    cdd65f: {nyc.get('cdd65f')} (expect ~1365)")


def main():
    parser = argparse.ArgumentParser(description='Enrich zipcode_lookup.json with HDD/CDD')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    args = parser.parse_args()

    print("Locating ComStock data root...")
    comstock_root = find_comstock_root()
    print(f"  Found ComStock at: {comstock_root}")

    print("\nBuilding cluster -> HDD/CDD mapping from ComStock data...")
    cluster_hdd_cdd = build_cluster_hdd_cdd(comstock_root)
    print(f"  {len(cluster_hdd_cdd)} clusters with HDD/CDD values")

    print("\nSaving cluster_hdd_cdd.json...")
    save_cluster_hdd_cdd(cluster_hdd_cdd, dry_run=args.dry_run)

    print("\nEnriching zipcode_lookup.json...")
    enrich_zipcode_lookup(cluster_hdd_cdd, dry_run=args.dry_run)

    print("\nDone.")


if __name__ == '__main__':
    main()
