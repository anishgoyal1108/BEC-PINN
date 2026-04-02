from .batch import run_batch
from .cache import manage_omega_cache
from .custom import run_custom_experiment
from .experiment_2x2 import run_2x2_threshold_experiment
from .movies import run_mass_density_phase_creator, run_movie_creator, run_movie_viewer
from .plotting import run_circulation_plotter
from .settings import (
    get_cache_status_summary,
    get_geometry_mode,
    get_imag_only_mode,
    get_sweep_mode,
    toggle_geometry_mode,
    toggle_imag_only_mode,
    toggle_sweep_mode,
)
from .solver import install_sigint_handler
from .transfer import (
    prompt_and_run_auto_omega_search,
    prompt_and_run_auto_transfer_search,
    run_transfer_vs_ubmax_plotter,
)


def _toggle_sweep_mode_with_message() -> None:
    new_mode = toggle_sweep_mode()
    if new_mode == "omega":
        print("\n  Sweep mode changed to: OMEGA (sweep over omega, fixed Ubmax)")
    else:
        print(
            "\n  Sweep mode changed to: UBMAX (sweep over Ubmax/temperature, fixed omega)"
        )


def _toggle_geometry_mode_with_message() -> None:
    new_mode = toggle_geometry_mode()
    print(f"\n  Geometry mode changed to: {new_mode.upper()}")


def _toggle_imag_mode_with_message() -> None:
    imag_only_mode = toggle_imag_only_mode()
    mode_label = "IMAGINARY ONLY" if imag_only_mode else "FULL (imag + real)"
    print(f"\n  Execution mode changed to: {mode_label}")


def main_menu():
    while True:
        mode_desc = (
            "UBMAX sweep (fixed omega)"
            if get_sweep_mode() == "ubmax"
            else "OMEGA sweep (fixed Ubmax)"
        )
        geometry_mode = get_geometry_mode().upper()
        imag_mode_label = "IMAG_ONLY" if get_imag_only_mode() else "FULL"
        cache_status = get_cache_status_summary()
        print("\n" + "=" * 60)
        print("FAST SIMULATION RUNNER - Main Menu (Generalized cache)")
        print(f"Current sweep mode: {mode_desc}")
        print(f"Current geometry mode: {geometry_mode}")
        print(f"Current execution mode: {imag_mode_label}")
        print(f"Ground state cache: {cache_status}")
        print("=" * 60)
        print("\n  1. Start Batch Run")
        print("  2. Create Movies for Existing Run")
        print("  3. View Movies for Existing Run")
        print("  4. Plot circulation.dat")
        print("  5. Manage Omega_r cache")
        print(
            "  6. Plot transfer summary (Ubmax vs wn if fixed omega; Omega_R vs wn if fixed Ubmax)"
        )
        print("  7. Mass-create density/phase images")
        print(
            "  8. AUTO Search (Critical Point Sweep) - Finds critical parameter for fixed condition"
        )
        print("  9. Run 2x2 Threshold Experiment")
        print("  10. Toggle Sweep Mode")
        print("  11. Toggle Geometry Mode (RING/TARGET)")
        print("  12. Toggle Execution Mode (FULL/IMAG_ONLY)")
        print("  13. Run Custom Experiment")
        print("  0/q. Quit")

        choice = input("\nSelect option: ").strip().lower()

        if choice in ("0", "q", "quit", "exit"):
            print("Goodbye!")
            break
        if choice == "1":
            run_batch()
        elif choice == "2":
            run_movie_creator()
        elif choice == "3":
            run_movie_viewer()
        elif choice == "4":
            run_circulation_plotter()
        elif choice == "5":
            manage_omega_cache()
        elif choice == "6":
            run_transfer_vs_ubmax_plotter()
        elif choice == "7":
            run_mass_density_phase_creator()
        elif choice == "8":
            if get_sweep_mode() == "omega":
                prompt_and_run_auto_omega_search()
            else:
                prompt_and_run_auto_transfer_search()
        elif choice == "9":
            run_2x2_threshold_experiment()
        elif choice == "10":
            _toggle_sweep_mode_with_message()
        elif choice == "11":
            _toggle_geometry_mode_with_message()
        elif choice == "12":
            _toggle_imag_mode_with_message()
        elif choice == "13":
            run_custom_experiment()
        else:
            print("Invalid option, try again.")


def main() -> None:
    install_sigint_handler()
    main_menu()
