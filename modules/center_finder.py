# from collections import defaultdict
# from findpeaks import findpeaks
# from scipy.interpolate import interp1d
# from scipy.ndimage import gaussian_filter

import h5py
import hdf5plugin
import numpy as np
from pyFAI.utils.ellipse import fit_ellipse
from typing import NamedTuple
import matplotlib.pylab as plt
from matplotlib import patches


def read_h5_data(file_name, group_name):
    with h5py.File(file_name, 'r') as hf_in:
        if isinstance(group_name, str):
            array = hf_in[group_name][()]
        else:
            array = []
            for dex, name in enumerate(group_name):
                array.append(hf_in[name][()])
    return array

# def find_common_elements(intensities, *lists):
#     """
#     Find the common coordinates in *lists then the their corresponding intensities from the first list (must be numpy array).
#     :param intensities:
#     :param lists:
#     :return:
#     """
#     list_of_tuples = [set(tuple(arr) for arr in lst) for lst in lists]
#     common_elements = list(set.intersection(*list_of_tuples))

#     common_intensities = [
#         intensities[np.where((lists[0] == coord).all(axis=1))[0][0]]
#         for coord in common_elements
#     ]

#     return common_elements, common_intensities



# def find_duplicate_indices(lst):
#     """
#     Returns the indices of the elements that appear more then once in the list.
#     :param lst:
#     :return:
#     """
#     indices_dict = defaultdict(list)
#     for idx, value in enumerate(lst):
#         indices_dict[value].append(idx)
#     duplicates = {key: indices for key, indices in indices_dict.items() if len(indices) > 1}
#     return duplicates


# def replace_zeros_with_cubic_interpolation(arr):
#     non_zero_indices = np.where(arr != 0)[0]
#     non_zero_values = arr[non_zero_indices]
#     interpolator = interp1d(non_zero_indices, non_zero_values, kind='cubic', fill_value="extrapolate")
#     interpolated_values = interpolator(np.arange(len(arr)))
#     arr = interpolated_values
#     return arr


# def peak_finding(cut, num_peaks, score_thresh):
#     fp = findpeaks(method='topology', verbose=0)
#     try:
#         peaks = fp.fit(replace_zeros_with_cubic_interpolation(np.array(cut)))
#     except ValueError:
#         return [], []

#     peaks_df = peaks['df'].loc[peaks['df']['peak'] == 1]
#     sorted_peaks = peaks_df.sort_values(by='rank', ascending=True)
#     sorted_peak_indices = sorted_peaks.index.tolist()
#     sorted_scores = sorted_peaks['score'].tolist()

#     # good_indices = [peak_index for dex, peak_index in enumerate(sorted_peak_indices[:num_peaks]) if sorted_scores[dex] > score_thresh]

#     return sorted_peak_indices[:num_peaks], sorted_peaks["y"][:num_peaks].tolist()
#     # return good_indices, sorted_peaks["y"][:len(good_indices)].tolist()


# def series_hor_cuts(diffraction, num_peaks=10, score_thresh=0):
#     coordinates = []
#     intensities = []
#     for dex, hor_cut in enumerate(diffraction):
#         peaks_indices, cut_intensities = peak_finding(hor_cut, num_peaks, score_thresh)
#         intensities.extend(cut_intensities)
#         coordinates.extend([np.array([dex, peak_index]) for peak_index in peaks_indices])
#     return np.array(coordinates), intensities


# def series_ver_cuts(diffraction, num_peaks=10, score_thresh=0):
#     coordinates = []
#     intensities = []
#     for dex, ver_cut in enumerate(diffraction.transpose()):
#         peaks_indices, cut_intensities = peak_finding(ver_cut, num_peaks, score_thresh)
#         intensities.extend(cut_intensities)
#         coordinates.extend([np.array([peak_index, dex]) for peak_index in peaks_indices])
#     return np.array(coordinates), intensities


# def center_beam_based_method(peak_coordinates, array_shape, intensities, thresh=1000):
#     circle_of_ones = np.zeros(array_shape, dtype="uint8")
#     center_beam_coors = []
#     for dex, coordinate in enumerate(peak_coordinates):
#         if intensities[dex] > thresh:
#             circle_of_ones[coordinate] = 10
#             center_beam_coors.append(coordinate)
#     center_beam_coors = np.array(center_beam_coors)
#     # print(center_beam_coors)

#     centers = []

#     for ver_hor in range(2):
#         coors = find_duplicate_indices(center_beam_coors[:, ver_hor])
#         # print(ver_hor, coors)
#         direction_centers = []
#         for coordinate_key in coors:
#             index_to_access = (ver_hor + 1) % 2
#             direction_centers.append((center_beam_coors[coors[coordinate_key][0]][index_to_access] +
#                                       center_beam_coors[coors[coordinate_key][1]][index_to_access]) / 2)

#         centers.append(float(np.mean(direction_centers)))

#     radius = float(
#         np.mean(np.sqrt((center_beam_coors[:, 1] - centers[0]) ** 2 + (center_beam_coors[:, 0] - centers[1]) ** 2)))

#     return np.array(centers), radius



# def find_image_center(image, pek_num=10, center_beam_threshold=20000):
    # mask = ~(np.load('log/full_dectris_mask.npy').astype(bool))
    # if type(image)==str:
    #     image = read_h5_data(image, "entry/data/data").squeeze() * mask
    
    # else: 
    #     image = image.squeeze()* mask
        
#     blured_image = gaussian_filter(image, sigma=1)
#     # print(np.max(blured_image))

#     hor_coors, hor_intensity = series_hor_cuts(blured_image, num_peaks=pek_num)
#     # print(len(hor_coors))
#     ver_coors, ver_intensity = series_ver_cuts(blured_image, num_peaks=pek_num)

#     for_center_coors, for_center_intensities = find_common_elements(hor_intensity, hor_coors, ver_coors)
#     # print(for_center_coors)
#     [x,y], circle_radius = \
#         center_beam_based_method(for_center_coors, blured_image.shape, for_center_intensities,
#                                  thresh=center_beam_threshold)

#     return np.array([y,x])



def find_image_center(image, center_beam_threshold=100):
    mask = ~(np.load('log/full_dectris_mask.npy').astype(bool))
    if type(image)==str:
        image = read_h5_data(image, "entry/data/data").squeeze() * mask
    
    else:
        image = image.squeeze() * mask

    image[image>1e7] = 0
    # com_coors = np.array([np.array([ver, hor]) for ver in range(image.shape[0]) for hor in range(image.shape[1]) if image[ver, hor] > center_beam_threshold])
    flat_indices = np.argsort(image.ravel())[-center_beam_threshold:]
    com_coors = np.column_stack(np.unravel_index(flat_indices, image.shape))
    

    try:
        y0, x0, angle, wlong, wshort = fit_ellipse(com_coors[:, 0], com_coors[:, 1])
    except ValueError:
        return np.array([np.nan,np.nan]), com_coors
    
    return np.array([y0, x0]), com_coors


