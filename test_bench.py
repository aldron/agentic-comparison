#!/usr/bin/env python3
"""Quick test of benchmark with both orchestrators using Claude."""
import runpy
import time

print("=" * 70)
print("FAIR FRAMEWORK COMPARISON")
print("Both orchestrators using Claude 3.5 Sonnet (same model)")
print("=" * 70)
start = time.time()
try:
    runpy.run_path('benchmarks/run_all.py', run_name='__main__')
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
elapsed = time.time() - start
print("=" * 70)
print(f"Total benchmark time: {elapsed:.2f}s")
print("=" * 70)
