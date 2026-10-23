"""Minimal balance task: train an AI controller for a 2-hip biped."""
from pathlib import Path
import gymnasium as gym
from gymnasium import spaces
import mujoco
import numpy as np

MODEL = Path(__file__).resolve().parents[1] / 'assets' / 'robot.xml'

class BalanceEnv(gym.Env):
    metadata = {'render_modes': ['human', 'rgb_array'], 'render_fps': 50}

    def __init__(self, render_mode=None):
        super().__init__()
        self.model = mujoco.MjModel.from_xml_path(str(MODEL))
        self.data = mujoco.MjData(self.model)
        self.render_mode = render_mode
        self.viewer = None
        self.renderer = None
        self.action_space = spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(17,), dtype=np.float32)
        self.steps = 0
        self.previous_action = np.zeros(2, dtype=np.float64)

    def _obs(self):
        return np.concatenate([self.data.qpos, self.data.qvel]).astype(np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[2] = 0.72
        self.data.qpos[3] = 1.0
        self.data.qpos[4:7] = 0.0
        self.data.qpos[7:9] = self.np_random.uniform(-0.05, 0.05, size=2)
        self.data.qvel[:] = self.np_random.normal(0, 0.015, size=self.model.nv)
        mujoco.mj_forward(self.model, self.data)
        self.steps = 0
        self.previous_action[:] = 0.0
        return self._obs(), {}

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=np.float64), -1, 1)
        self.data.ctrl[:] = action
        for _ in range(2):
            mujoco.mj_step(self.model, self.data)
        self.steps += 1
        height = float(self.data.qpos[2])
        torso = self.data.body('torso').xmat.reshape(3, 3)
        upright = float(torso[2, 2])
        alive = height > 0.40 and upright > 0.55
        # Shape reward around stable, smooth balancing rather than survival alone.
        # Keep survival as the dominant incentive and avoid rewarding early falls.
        angular_speed = float(np.linalg.norm(self.data.qvel[3:6]))
        height_error = abs(height - 0.72)
        effort = float(np.sum(action ** 2))
        action_change = float(np.sum((action - self.previous_action) ** 2))
        reward = (
            2.0
            + 2.0 * upright
            - 0.8 * height_error
            - 0.08 * angular_speed
            - 0.08 * effort
            - 0.06 * action_change
        ) if alive else -10.0
        self.previous_action[:] = action
        terminated = not alive
        truncated = self.steps >= 500
        if self.render_mode == 'human':
            self.render()
        return self._obs(), reward, terminated, truncated, {'height': height, 'upright': upright, 'survived_seconds': self.steps * 0.02}

    def render(self):
        if self.render_mode == 'human':
            if self.viewer is None:
                import mujoco.viewer
                self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
            self.viewer.sync()
        elif self.render_mode == 'rgb_array':
            if self.renderer is None:
                self.renderer = mujoco.Renderer(self.model, 480, 640)
            self.renderer.update_scene(self.data)
            return self.renderer.render()

    def close(self):
        if self.viewer is not None:
            self.viewer.close()
            self.viewer = None
        if self.renderer is not None:
            self.renderer.close()
            self.renderer = None
