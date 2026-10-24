"""Stateless observation-only hip torque control; all gains are physical Nm units."""
import numpy as np

GEARS = np.array([45., 35.])


class Feedback:
    def __init__(self, parameters):
        self.parameters = dict(parameters)

    def predict(self, observation, deterministic=True):
        obs = np.asarray(observation, dtype=float)
        if obs.shape != (17,) or not np.isfinite(obs).all():
            raise ValueError('Expected finite 17-dimensional state observation')
        quat = obs[3:7]
        norm = np.linalg.norm(quat)
        if norm < 1e-8:
            raise ValueError('Invalid quaternion')
        w,x,y,z = quat/norm  # MuJoCo wxyz; positive pitch rotates +z toward +x.
        pitch = np.arctan2(2*(x*z+w*y), 1-2*(x*x+y*y))
        p = self.parameters
        common = p.get('pitch_k',0.)*pitch + p.get('pitch_d',0.)*obs[13]
        tau = (-p.get('hip_k',0.)*obs[7:9] - p.get('hip_d',0.)*obs[15:17]
               + .5*common + p.get('bias_Nm',0.))
        return np.clip(tau/GEARS,-1.,1.).astype(np.float32), None


def gain_grid():
    rows = [dict(name='zero'), dict(name='hip_PD_8',hip_k=8.,hip_d=1.),
            dict(name='bias_positive',bias_Nm=.02),dict(name='bias_negative',bias_Nm=-.02)]
    for hip_k in (2.,8.,32.,128.):
        for pitch_k,pitch_d in ((0.,0.),(4.,.5),(16.,1.),(64.,2.),(0.,2.),(16.,4.),(64.,8.)):
            rows.append(dict(name=f'hip{hip_k:g}_pitch{pitch_k:g}_d{pitch_d:g}',hip_k=hip_k,
                             hip_d=float(2*np.sqrt(.03*hip_k)),pitch_k=pitch_k,pitch_d=pitch_d))
    assert len(rows)==32
    return rows
