#
#

import numpy as np
import pyvista as pv
from numba import jit
from pycoatl.spatialdata.spatialdata import SpatialData

def interpolate_spatialdata_grid(spatialdata,spacing=0.2):
    """Interpolate spatial data to a regular grid with given spacing.
    Used as part of the DIC simulation.

    Args:
        spatialdata (SpatialData): SpatialData instance containing FE data
        spacing (float, optional): Grid spacing in mm. Defaults to 0.2.

    Returns:
        SpatialData: A new SpatialData instance with the interpolated data.
    """
    bounds = spatialdata.data_sets[0].bounds
    # Create regular grid to interpolate to
    xr = np.linspace(bounds[0],bounds[1],int((bounds[1]-bounds[0])/spacing))
    yr = np.linspace(bounds[2],bounds[3],int((bounds[3]-bounds[2])/spacing))
    zr = bounds[5]
    x,y,z = np.meshgrid(xr,yr,zr)
    grid = pv.StructuredGrid(x,y,z)

    # Possibly want to add tag to metadata to say it's processed.
    metadata = spatialdata._metadata
    metadata['interpolated'] = True
    metadata['interpolation_type'] = 'grid'
    metadata['grid_spacing'] = spacing
    
    data_sets_int = []
    for mesh in spatialdata.data_sets:
        result = grid.sample(mesh)
        for field in result.array_names:
            if field not in ['ObjectId','vtkGhostType','vtkValidPointMask','vtkGhostType']:
                result[field][result['vtkValidPointMask']==False] =np.nan
        data_sets_int.append(result)

    mb_interpolated = SpatialData(data_sets_int,spatialdata._index,spatialdata._time,spatialdata._load,metadata)
    return mb_interpolated


def get_points_neighbours(mesh,window_size=5):
    """Get the neighbouring points for a mesh.
    Initial phase of the window differentiation.
    Assumes a regular-like quad mesh. Such that surrounding each point are 
    8 others.

    Args:
        mesh (pyvista unstructured mesh): Mesh file to characterise.
        window_size (int, optional): Size of the subwindow to differentiate over. Defaults to 5.

    Returns:
        array: Connectivity array, listing window indices for each point.
    """

    n_points = mesh.number_of_points
    levels = int((window_size -1)/2)
    points_array = []# = np.empty((n_points,int(window_size**2)))
    
    for point in range(n_points):
        #point = 0
        point_neighbours = mesh.point_neighbors_levels(point,levels)
        point_neighbours = list(point_neighbours)
        #print(point_neighbours)
        neighbours = [point]
        for n in point_neighbours:
            neighbours = neighbours + n
        #print(neighbours)
        points_array.append(neighbours)
    return points_array


def window_differentation(spatialdata,data_range = 'all',window_size=5):
    """Differentiate spatialdata using subwindow approach to 
    mimic DIC filter. Adds the differentiated fields into the meshes in
    the supplied spatial data.

    Args:
        spatialdata (SpatialData): SpatialData instance from FE
        data_range (str, optional): Differentiate all time steps, or just last one. Should be 'all' or 'last'. Defaults to 'all'.
        window_size (int, optional): Subwindow size. Defaults to 5.
    """
    points_list = get_points_neighbours(spatialdata.data_sets[0],window_size)


    @jit(nopython=True)
    def L_Q4_n(x):
        
        return np.vstack((np.ones(x[0].shape),x[0],x[1],x[0]*x[1])).T

    @jit(nopython=True)
    def evaluate_point_dev_n(point_data,data):
        """
        Fit an calculate deformation gradient at each point.
        """
        window_spread = int((window_size - 1) /2)
        
        xdata = point_data[:,:2].T
        xbasis = L_Q4_n(xdata)
        ydata = data.ravel()

        if len(ydata)<window_size**2:
            partial_dx = np.nan
            partial_dy = np.nan
        else:
            paramsQ4, r, rank, s = np.linalg.lstsq(xbasis, ydata)
                
            px = xdata[:,int(round((window_size**2) /2))]
            partial_dx = paramsQ4[1] + paramsQ4[3]*px[1]
            partial_dy = paramsQ4[2] + paramsQ4[3]*px[0]
            
        return partial_dx, partial_dy

    @jit(nopython=True)    
    def euler_almansi_n(dudx,dudy,dvdx,dvdy):
        """
        Calculates the Euler-Almansi strain tensor from the given gradient data.
        Can implement more in future.
        """
        #exx = dudx - 0.5*(dudx**2+dvdx**2)
        exx = np.log(np.sqrt(1 + 2*dudx + dudx**2 + dudy**2))
        #eyy = dvdy - 0.5*(dvdy**2+dudy**2)
        eyy = np.log(np.sqrt(1 + 2*dvdy + dvdx**2 + dvdy**2))
        #exy = 0.5*(dudy + dvdx) - 0.5*((dudx*dudy)+(dvdx*dvdy))
        exy = dvdx*(1+dudx) + dudy*(1+dvdy)
        return exx,eyy,exy
    
    def differentiate_mesh(mesh,points_list):
        n_points = mesh.number_of_points
        dudx = np.empty(n_points)
        dvdx = np.empty(n_points)
        dudy = np.empty(n_points)
        dvdy = np.empty(n_points)

        for point in range(n_points):
            #point = 0
            neighbours = points_list[point]
            point_data = mesh.points[neighbours]
            #x_coords = point_data[:,0]
            #y_coords = point_data[:,1]
            u = mesh.point_data['disp_x'][neighbours]
            v = mesh.point_data['disp_y'][neighbours]
            
            dudx[point],dudy[point] = evaluate_point_dev_n(point_data,u)
            dvdx[point],dvdy[point] = evaluate_point_dev_n(point_data,v)

        exx,eyy,exy = euler_almansi_n(dudx,dudy,dvdx,dvdy)

        return exx,eyy,exy
    # Update meta data
    spatialdata._metadata['dic_filter'] = True
    spatialdata._metadata['window_size'] = window_size
    spatialdata._metadata['data_range'] = data_range
    # Iterate over meshes, but ignore metadata which is in posn 0
    if data_range == 'all':
        for mesh in spatialdata.data_sets:
            exx,eyy,exy = differentiate_mesh(mesh,points_list)
            mesh['exx'] =exx
            mesh['eyy'] =eyy
            mesh['exy'] =exy
    elif data_range =='last':
        mesh = spatialdata.data_sets[-1]
        exx,eyy,exy = differentiate_mesh(mesh,points_list)
        mesh['exx'] =exx
        mesh['eyy'] =eyy
        mesh['exy'] =exy


def get_standard_theme():
    standard_theme = pv.themes.DocumentTheme()
    standard_theme.colorbar_orientation = 'vertical'
    standard_theme.colorbar_vertical.position_x = 0.75
    standard_theme.font.family = 'arial'
    standard_theme.font.size = 20
    standard_theme.camera = {'position': [0,0,1],'viewup':[0,1,0]}

    return standard_theme
