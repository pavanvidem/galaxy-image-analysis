import argparse
import sys
import warnings

import giatools.io
import numpy as np
import skimage.color
import skimage.io
import skimage.util
import tifffile
from sklearn.decomposition import FactorAnalysis, FastICA, NMF, PCA

# Stain separation matrix for H&E color deconvolution, extracted from ImageJ/FIJI
rgb_from_he = np.array([
    [0.64431860, 0.7166757, 0.26688856],
    [0.09283128, 0.9545457, 0.28324000],
    [0.63595444, 0.0010000, 0.77172660],
])

convOptions = {
    # General color space conversion operations
    'hed2rgb': lambda img_raw: skimage.color.hed2rgb(img_raw),
    'hsv2rgb': lambda img_raw: skimage.color.hsv2rgb(img_raw),
    'lab2lch': lambda img_raw: skimage.color.lab2lch(img_raw),
    'lab2rgb': lambda img_raw: skimage.color.lab2rgb(img_raw),
    'lab2xyz': lambda img_raw: skimage.color.lab2xyz(img_raw),
    'lch2lab': lambda img_raw: skimage.color.lch2lab(img_raw),
    'luv2rgb': lambda img_raw: skimage.color.luv2rgb(img_raw),
    'luv2xyz': lambda img_raw: skimage.color.luv2xyz(img_raw),
    'rgb2hed': lambda img_raw: skimage.color.rgb2hed(img_raw),
    'rgb2hsv': lambda img_raw: skimage.color.rgb2hsv(img_raw),
    'rgb2lab': lambda img_raw: skimage.color.rgb2lab(img_raw),
    'rgb2luv': lambda img_raw: skimage.color.rgb2luv(img_raw),
    'rgb2rgbcie': lambda img_raw: skimage.color.rgb2rgbcie(img_raw),
    'rgb2xyz': lambda img_raw: skimage.color.rgb2xyz(img_raw),
    'rgbcie2rgb': lambda img_raw: skimage.color.rgbcie2rgb(img_raw),
    'xyz2lab': lambda img_raw: skimage.color.xyz2lab(img_raw),
    'xyz2luv': lambda img_raw: skimage.color.xyz2luv(img_raw),
    'xyz2rgb': lambda img_raw: skimage.color.xyz2rgb(img_raw),

    # Color deconvolution operations
    'hed_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.hed_from_rgb),
    'hdx_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.hdx_from_rgb),
    'fgx_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.fgx_from_rgb),
    'bex_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.bex_from_rgb),
    'rbd_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.rbd_from_rgb),
    'gdx_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.gdx_from_rgb),
    'hax_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.hax_from_rgb),
    'bro_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.bro_from_rgb),
    'bpx_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.bpx_from_rgb),
    'ahx_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.ahx_from_rgb),
    'hpx_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, skimage.color.hpx_from_rgb),

    # Recomposition operations (reverse color deconvolution)
    'rgb_from_hed': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_hed),
    'rgb_from_hdx': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_hdx),
    'rgb_from_fgx': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_fgx),
    'rgb_from_bex': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_bex),
    'rgb_from_rbd': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_rbd),
    'rgb_from_gdx': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_gdx),
    'rgb_from_hax': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_hax),
    'rgb_from_bro': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_bro),
    'rgb_from_bpx': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_bpx),
    'rgb_from_ahx': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_ahx),
    'rgb_from_hpx': lambda img_raw: skimage.color.combine_stains(img_raw, skimage.color.rgb_from_hpx),

    # Custom color deconvolution and recomposition operations
    'rgb_from_he': lambda img_raw: skimage.color.combine_stains(img_raw, rgb_from_he),
    'he_from_rgb': lambda img_raw: skimage.color.separate_stains(img_raw, np.linalg.inv(rgb_from_he)),

    # Unsupervised machine learning-based operations
    'pca': lambda img_raw: np.reshape(PCA(n_components=3).fit_transform(np.reshape(img_raw, [-1, img_raw.shape[2]])),
                                      [img_raw.shape[0], img_raw.shape[1], -1]),
    'nmf': lambda img_raw: np.reshape(NMF(n_components=3, init='nndsvda').fit_transform(np.reshape(img_raw, [-1, img_raw.shape[2]])),
                                      [img_raw.shape[0], img_raw.shape[1], -1]),
    'ica': lambda img_raw: np.reshape(FastICA(n_components=3).fit_transform(np.reshape(img_raw, [-1, img_raw.shape[2]])),
                                      [img_raw.shape[0], img_raw.shape[1], -1]),
    'fa': lambda img_raw: np.reshape(FactorAnalysis(n_components=3).fit_transform(np.reshape(img_raw, [-1, img_raw.shape[2]])),
                                     [img_raw.shape[0], img_raw.shape[1], -1])
}

parser = argparse.ArgumentParser()
parser.add_argument('input_file', type=argparse.FileType('r'), default=sys.stdin, help='input file')
parser.add_argument('out_file', type=argparse.FileType('w'), default=sys.stdin, help='out file (TIFF)')
parser.add_argument('conv_type', choices=convOptions.keys(), help='conversion type')
parser.add_argument('--isolate_channel', type=int, help='set all other channels to zero (1-3)', default=0)
args = parser.parse_args()

# Read and normalize the input image as TZYXC
img_in = giatools.io.imread(args.input_file.name)

# Verify input image
assert img_in.shape[0] == 1, f'Image must have 1 frame (it has {img_in.shape[0]} frames)'
assert img_in.shape[1] == 1, f'Image must have 1 slice (it has {img_in.shape[1]} slices)'
assert img_in.shape[4] == 3, f'Image must have 3 channels (it has {img_in.shape[4]} channels)'

# Normalize the image from TZYXC to YXC
img_in = img_in.squeeze()
assert img_in.ndim == 3

# Apply channel isolation
if args.isolate_channel:
    for ch in range(3):
        if ch + 1 != args.isolate_channel:
            img_in[:, :, ch] = 0

result = convOptions[args.conv_type](img_in)

# It is sufficient to store 32bit floating point data, the precision loss is tolerable
if result.dtype == np.float64:
    result = result.astype(np.float32)

with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    tifffile.imwrite(args.out_file.name, result)
