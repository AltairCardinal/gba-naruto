"""The X2 stream -- the same semantics walk for the S49 fidelity bench.

The judgment bench measured 86 % of its residual as "pairing diff": the two
sides were at different game moments.  This package builds the walk that puts
both sides at the same moment:

* :mod:`tools.s49_pairing.walkspec` -- the shared semantic script and the two
  sides' translations of it.
* :mod:`tools.s49_pairing.record` -- records the walk (frame **and** savestate
  per sample).
* :mod:`tools.s49_pairing.savestate` -- reads a savestate without the probe.
* :mod:`tools.s49_pairing.anchors` -- the dense content anchor (two
  dimensional camera, overlay family set, screen facts, acting pointer).
* :mod:`tools.s49_pairing.pair` -- the pairing table and the reachability
  bound.
"""

__version__ = "1.0.0"
