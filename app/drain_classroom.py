import argparse
import asyncio
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from openwebui_bridge.client import BridgeClient

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root', required=True)
    parser.add_argument('--port', type=int, default=8790)
    args = parser.parse_args()
    asyncio.run(BridgeClient.from_config(args.data_root, args.port).control('drain'))
    print('Classroom provider connections drained.')
