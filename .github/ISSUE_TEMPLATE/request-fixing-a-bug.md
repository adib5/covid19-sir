---
name: Request fixing a bug
about: Customized issue template for fixing a bug.
title: ''
labels: bug
assignees: ''

---

## Summary
Please edit this to explain the summary of the bug.
`` needs to return ... but returns ...

## Related classes
- `covsirphy.`
(optional)

## Codes and outputs:
```Python
import covsirphy as cs
# Dataset preparation
data_loader = cs.DataLoader("input")
jhu_data = data_loader.jhu()
population_data = data_loader.population()
```
This code returns 

## Environment
- CovsirPhy version: 
- Python version; 3.8
- Installation: pipenv
- OS: Windows/WSL/Linux/MAC/Kaggle Notebook
