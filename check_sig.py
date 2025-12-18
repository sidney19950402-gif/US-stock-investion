import inspect
from strategy import MomentumStrategy

sig = inspect.signature(MomentumStrategy.generate_signals)
print(f"Signature: {sig}")
if 'lookbacks' in sig.parameters:
    print("SUCCESS: lookbacks parameter found.")
else:
    print("FAILURE: lookbacks parameter NOT found.")
