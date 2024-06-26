import numpy as np
import argparse
from classy import Class
from pyDOE import lhs
import h5py


def setup(args):

    parser = argparse.ArgumentParser(description='Create a bank of power spectra for a given cosmology')
    parser.add_argument('--n_pk', type=int, default=100, help='Number of power spectra to generate')
    parser.add_argument('--n_k', type=int, default=100, help='Number of k values to use')
    parser.add_argument('--spec_per_ind', type=int, default=500, help='Number of spectra per index')
    parser.add_argument('--output_dir', type=str, default='pk_bank', help='Directory to save the power spectra')

    args = parser.parse_args(args)

    # Define the ranges for your parameters: (min, max)

    planck_mean = {'omega_b': 0.02235, 'omega_cdm': 0.120, 'h': 0.675, 'ln10^{10}A_s': 3.044, 'n_s': 0.965, 'Omega_k': 0., 'N_ncdm': 1., 'm_ncdm': 0.06, 'T_ncdm': 0.71611, 'N_ur': 2.0329, 'w0_fld': -1, 'Omega_Lambda': 0.}

    lss_sigma = {'omega_b': 0.00035, 'omega_cdm': 0.010, 'h': 0.015, 'ln10^{10}A_s': 0.15, 'n_s': 0.060, 'w0_fld': 0.03, 'm_ncdm': 0.2, 'N_ur': 0.2, 'Omega_k': 0.05}


    #these are planck bestfit +- 5 lss sigma
    param_ranges = {
        "omega_cdm": [planck_mean["omega_cdm"] - 5*lss_sigma["omega_cdm"], planck_mean["omega_cdm"]+5*lss_sigma["omega_cdm"]],   # omega_cdm
        "omega_b": [planck_mean["omega_b"] - 5*lss_sigma["omega_b"], planck_mean["omega_b"]+5*lss_sigma["omega_b"]], # omega_b
        "h": [planck_mean["h"]-5*lss_sigma["h"], planck_mean["h"] + 5* lss_sigma["h"]],   # h
        "Omega_k": [planck_mean["Omega_k"]- 5*lss_sigma["Omega_k"], planck_mean["Omega_k"] + 5*lss_sigma["Omega_k"]],    # curvature
        # "sigma8": [planck_mean["sigma8"]-5*lss_sigma["sigma8"], planck_mean["sigma8"]+5*lss_sigma["sigma8"]],   # sigma_8 #we dont not vary sigma8 as this is just a normalization parameter
        "n_s": [planck_mean["n_s"] - 5* lss_sigma["n_s"], planck_mean["n_s"] + 5* lss_sigma["n_s"]],    # n_s
        "N_ur":[planck_mean["N_ur"] - 5* lss_sigma["N_ur"], planck_mean["N_ur"] + 5* lss_sigma["N_ur"]], # N_ur
        "m_ncdm":[planck_mean["m_ncdm"] - 5* lss_sigma["m_ncdm"], planck_mean["m_ncdm"] + 5* lss_sigma["m_ncdm"]], # m_ncdm
        "w0_fld":[planck_mean["w0_fld"] - 5* lss_sigma["w0_fld"], planck_mean["w0_fld"] + 5* lss_sigma["w0_fld"]], # w0_fld
        "z":[0,4]
    }

    return args, param_ranges

def merge(indices, args) 
    args, param_ranges = setup(args)

    with h5py.File(args.output_dir + '/total_data.h5', 'a') as hdf_file:
        # Function to load and save data to HDF5
        def update_or_create_dataset(dataset_name, data):
            if dataset_name in hdf_file:
                # Dataset exists, append the data to the existing dataset
                hdf_file[dataset_name].resize((hdf_file[dataset_name].shape[0] + data.shape[0]), axis=0)
                hdf_file[dataset_name][-data.shape[0]:] = data
            else:
                # Dataset doesn't exist, create it
                hdf_file.create_dataset(dataset_name, data=data, maxshape=(None, None))

        for index in indices:
            # Load the processed results for the current index from the npz file
            npz_file_path = args.output_dir + f'/pk_{index}.npz'

            try:
                with np.load(npz_file_path, mmap_mode='r') as data:
                    datasets = ["pk_lin","params"]

                    for dataset in datasets:
                        update_or_create_dataset(dataset, data[dataset])

            except:
                print(f"could not load file for index: {index}")

def main(indices, args):

    args, param_ranges = setup(args)

    #sample over a latin hypercube to get the sets of cosmology to cpmpute pk for and the z value to use 
    #for each cosmology

    #set up the cosmology parameters


    #set up the k values to use
    kk = np.logspace(-5, 1, args.n_k)

    #get the LHS samples 
    lhs_samples = lhs(n=len(param_ranges.keys()), samples=args.n_pk, criterion='center')

    scaled_samples = {}
    for i, key in enumerate(param_ranges.keys()):
        min_val, max_val = param_ranges[key]
        scaled_samples[key] = lhs_samples[:, i] * (max_val - min_val) + min_val


    for index in indices: 

            #set up the array to store the power spectra
        pk = np.zeros((args.spec_per_ind, args.n_k))

        #Select a subset if of the scaled samples
        subset = {key: scaled_samples[key][index*args.spec_per_ind:(index+1)*(args.spec_per_ind)] for key in scaled_samples.keys()}

        for i in range(args.spec_per_ind):
            #set up the class object
            cosmo = Class()
            #set the parameters
            cosmo.set({key: subset[key][i] for key in subset.keys() if key not in ['z']})
            #compute the power spectrum
            cosmo.set({"output":"mPk", 
                        "N_ncdm": 1,
                        "T_ncdm": 0.71611,
                        "Omega_Lambda": 0,
                       "P_k_max_1/Mpc": 30.,
                       'z_max_pk': subset['z'][i]})
            cosmo.compute()

            pk[i] = np.array([cosmo.pk_lin(k*cosmo.h(), subset["z"][i])*cosmo.h()**3 for k in kk])

        
        #turn all fo the parameter values stored in the subset dict into a numpy array
        param_values = np.array([subset[key] for key in subset.keys()]).T

        np.savez(args.output_dir + "/pk_" + str(index), pk_lin=pk, params=param_values)
        
        yield indices 

