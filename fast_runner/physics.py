def ubmax_scaled_from_T_nK(T_nK: float) -> float:
    hbar = 1.0546e-34
    atom_mass = 23.0 * 1.66e-27
    L0 = 10.0e-6
    kB = 1.38e-23
    E0 = hbar**2 / (2.0 * atom_mass * L0**2)
    T_K = T_nK * 1e-9
    return (kB * T_K) / E0


def T_nK_from_ubmax_seu(ubmax_seu: float) -> float:
    hbar = 1.0546e-34
    atom_mass = 23.0 * 1.66e-27
    L0 = 10.0e-6
    kB = 1.38e-23
    E0 = hbar**2 / (2.0 * atom_mass * L0**2)
    T_K = (ubmax_seu * E0) / kB
    return T_K * 1e9
