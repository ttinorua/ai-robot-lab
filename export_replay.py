"""Export a deterministic PPO rollout to a mobile-friendly 3D replay JSON.

Coordinate conversion is handled by the viewer (MuJoCo uses z-up).
"""
import argparse
import json
from pathlib import Path

from stable_baselines3 import PPO
from robot_lab import BalanceEnv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/balance_ppo.zip")
    parser.add_argument("--output", default="replays/trained-robot.json")
    parser.add_argument("--seed", type=int, default=1000)
    args = parser.parse_args()

    env = BalanceEnv()
    policy = PPO.load(args.model)
    observation, _ = env.reset(seed=args.seed)
    frames = []

    def record():
        q = env.data.qpos
        frames.append({
            "position": [float(v) for v in q[:3]],
            "quaternion": [float(v) for v in q[3:7]],
            "hips": [float(v) for v in q[7:9]],
        })

    record()
    for _ in range(500):
        action, _ = policy.predict(observation, deterministic=True)
        observation, _, terminated, truncated, info = env.step(action)
        record()
        if terminated or truncated:
            break

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "format": "ai-robot-lab-replay-v1",
        "source": "trained PPO policy",
        "step_seconds": 0.02,
        "seed": args.seed,
        "survived_seconds": round((len(frames) - 1) * 0.02, 2),
        "frames": frames,
    }, separators=(",", ":")), encoding="utf-8")
    env.close()
    print(f"Saved {len(frames)} frames to {output}; duration {(len(frames)-1)*0.02:.2f}s")


if __name__ == "__main__":
    main()
