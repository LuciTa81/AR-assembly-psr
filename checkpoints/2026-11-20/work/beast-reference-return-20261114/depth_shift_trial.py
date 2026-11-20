"""Offline five-parameter hypothesis; never activates a calibration."""

import numpy as np
from scipy.optimize import minimize_scalar


def predict(matrices, xyz, shift=0.0, bias=None):
    matrices, xyz = np.asarray(matrices, float), np.asarray(xyz, float)
    bias = np.zeros((2, 2)) if bias is None else np.asarray(bias, float)
    if (matrices.shape != (2, 3, 4) or xyz.ndim != 2 or xyz.shape[1] != 3
            or bias.shape != (2, 2) or not np.isfinite(shift)
            or not all(np.isfinite(a).all() for a in (matrices, xyz, bias))):
        raise ValueError("Invalid eye matrices, coordinates or offsets")
    points = np.column_stack([xyz[:, :2], xyz[:, 2] + shift, np.ones(len(xyz))])
    q = np.einsum('eij,nj->nei', matrices, points)
    if (xyz[:, 2] <= 0).any() or (q[:, :, 2] <= 1e-6).any():
        raise ValueError("Nonpositive projection depth")
    return q[:, :, :2] / q[:, :, 2:] + bias


def fit(matrices, xyz, pixels):
    xyz, pixels = np.asarray(xyz, float), np.asarray(pixels, float)
    if (xyz.ndim != 2 or xyz.shape[1] != 3 or len(xyz) < 2
            or pixels.shape != (len(xyz), 2, 2) or not np.isfinite(pixels).all()
            or len(np.unique(xyz, axis=0)) != len(xyz)):
        raise ValueError("At least two distinct paired observations required")
    predict(matrices, xyz)
    predict(matrices, xyz, -100.)
    predict(matrices, xyz, 300.)

    def evaluate(shift):
        predicted = predict(matrices, xyz, shift)
        bias = np.mean(pixels - predicted, axis=0)
        return float(np.sum((predicted + bias - pixels) ** 2)), bias

    result = minimize_scalar(lambda z: evaluate(z)[0], bounds=(-100., 300.),
                             method='bounded', options={'xatol': 1e-9})
    cost, bias = evaluate(result.x)
    if not result.success or cost > min(evaluate(z)[0] for z in np.linspace(-100., 300., 81)) + 1e-6:
        raise ValueError("Scalar fit failed independent coarse-grid check")
    return dict(shift_mm=float(result.x), bias_px=bias.tolist(), squared_error=cost,
                bounds_mm=[-100., 300.], bound_hit=bool(abs(result.x+100.) < .01 or abs(result.x-300.) < .01))


def shifted_matrices(matrices, shift, bias):
    matrices, bias = np.asarray(matrices, float), np.asarray(bias, float)
    if matrices.shape != (2, 3, 4) or bias.shape != (2, 2) or not all(
            np.isfinite(a).all() for a in (matrices, bias, np.asarray(shift))):
        raise ValueError("Invalid matrix transform")
    result = matrices.copy()
    result[:, :, 3] += shift * result[:, :, 2]
    result[:, :2, :] += bias[:, :, None] * result[:, 2:3, :]
    return result
