"""Content pruning: DOM -> pruned DOM.

Separates main content from navigation, footers, ads, and other boilerplate.

Implementation constraint: a single bottom-up traversal, O(N). Do not
re-walk subtrees per node.
"""
