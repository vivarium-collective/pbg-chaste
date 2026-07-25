"""pbg-chaste: process-bigraph wrapper for the Chaste cell-based simulator.

Exposes Chaste's multi-cellular population methods (mesh/vertex/node) and
sub-cellular cell-cycle models (uniform/stochastic/tyson_novak/delta_notch) as
one parametrized :class:`ChasteSimulationProcess`, driving the real engine
through the chaste/pychaste Docker image.
"""

from .processes import (
    ChasteSimulationProcess,
    ChasteCellSortingProcess,
    POPULATIONS,
    CELL_CYCLES,
    SORTING_MODELS,
)

# Registering the @composite_generator entries needs viva_superpowers (provided
# by the pbg ecosystem / plugin). Guard it so the core Process stays importable
# even in a bare install without viva_superpowers.
try:
    from . import composites  # noqa: F401
except ImportError:  # pragma: no cover
    composites = None

__all__ = [
    "ChasteSimulationProcess",
    "ChasteCellSortingProcess",
    "POPULATIONS",
    "CELL_CYCLES",
    "SORTING_MODELS",
]
