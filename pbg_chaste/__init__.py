"""pbg-chaste: process-bigraph wrapper for the Chaste cell-based simulator.

Exposes Chaste's multi-cellular population methods (mesh/vertex/node) and
sub-cellular cell-cycle models (uniform/stochastic/tyson_novak/delta_notch) as
one parametrized :class:`ChasteSimulationProcess`, driving the real engine
through the chaste/pychaste Docker image.
"""

from .processes import ChasteSimulationProcess, POPULATIONS, CELL_CYCLES
from . import composites  # noqa: F401  (registers @composite_generator entries)

__all__ = ["ChasteSimulationProcess", "POPULATIONS", "CELL_CYCLES"]
