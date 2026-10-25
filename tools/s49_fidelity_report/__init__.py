"""The S49 fidelity judgment bench.

The bench is the acceptance instrument of the "木叶丸 vs 野蜂" replication:
it re-records the original and the remake, aligns them, measures the
battlefield residual and attributes every frame of it.

The package is split into the pieces the bench is made of:

``paths``        the shared constants (geometry, thresholds, the outline wave).
``capture``      re-recording the two walks with the headless probe.
``probe``        reading the machine state of a captured step (IO, PRAM, VRAM).
``anchors``      the content anchors: what the state says about each frame.
``pixels``       the pixel maths (residual, structure, brightness, outline).
``overlay``      the per-cell overlay family map -- the second residual axis.
``staticframes`` the static frame criterion (flat spot or defect).
``classify``     the attribution, including the three buckets of a pairing diff.
``ratchet``      the gate: the residual is only allowed to get smaller.
``report``       assembling the report and rendering its Markdown receipt.
"""

__version__ = "2.0.0"
