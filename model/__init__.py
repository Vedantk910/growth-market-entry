"""C2 market-entry model: sizing -> unit economics -> decision surface.

Pure functions over ``data.facts.Facts`` (numpy/pandas only, offline):

  - sizing         : SAM -> serviceable -> capturable funnel at stated
                     capture rate and CAC (the top-down block a partner
                     screenshots).
  - unit_economics : contribution margin per parcel by route, the fixed-cost
                     allocation, and the in-house break-even volume.
  - decision       : the 3-D enter / partner / decline sweep (cost decay
                     x partner rate x in-house variable cost) with the
                     zero-line as the decision boundary, and the trigger
                     line.  The partner-screenshot artifact.
"""
from . import sizing, unit_economics, decision
