#
# Testing new Lloyd's new implementation of exodus reader
#
#%%
from mooseherder.exodusreader import ExodusReader
import netCDF4 as nc
import numpy as np
from pycoatl.spatialdata.importmoose import moose_to_spatialdata
import pyvista as pv

# %%
test = ExodusReader('D:\Rory\Spyder\pycoatl\data\moose_output.e')
# %%
test.node_var_names
# %%
print(test.node_data['creep_strain_yy'])
# %%
efile = 'D:\Rory\Spyder\pycoatl\data\moose_output.e'
data = nc.Dataset(efile)
# %%
efile = '/home/rspencer/pycoatl/data/moose_output.e'
test = moose_to_spatialdata(efile)
# %%
efile = '/home/rspencer/mooseherder/examples/moose-workdir-1/moose-sim-1_out.e'
test = moose_to_spatialdata(efile)
# %%
test = pv.read_exodus(efile)
# %%
test2=ExodusReader(efile)
# %%
test3 = nc.Dataset(efile)
# %%
efile3 = '/home/rspencer/pycoatl/data/moose_output.e'
test3=ExodusReader(efile3)
# %%
