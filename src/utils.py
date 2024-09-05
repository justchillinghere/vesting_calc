from typing import Dict, List, Optional, Union, Iterable


def round_to_precision(value, precision=10**7, decimal_places=4):
    rounded = round(value / precision, decimal_places)
    if rounded % 1 == 0:
        return int(rounded)
    return rounded


def group_consecutive_epochs(epochs):
    if not epochs:
        return []
    epochs = sorted(epochs)
    groups = []
    current_group = [epochs[0]]
    for epoch in epochs[1:]:
        if epoch == current_group[-1] + 1:
            current_group.append(epoch)
        else:
            groups.append(current_group)
            current_group = [epoch]
    groups.append(current_group)
    return groups
