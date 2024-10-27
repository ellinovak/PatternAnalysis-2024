import os
from typing import Sequence, Mapping

import numpy as np
from utils import load_data_3D
from monai.transforms import (Compose, ToTensord, Spacingd, EnsureChannelFirstd, ScaleIntensityRanged, CropForegroundd,
                              Orientationd, RandCropByPosNegLabeld, Affined)
from torch.utils.data import Dataset, DataLoader
from torch.utils.data._utils.collate import default_collate

# test other transforms
train_transforms = Compose(
    [
        EnsureChannelFirstd(keys=["image", "label"]),
        ScaleIntensityRanged(
            keys=["image"],
            a_min=-57,
            a_max=164,
            b_min=0.0,
            b_max=1.0,
            clip=True,
        ),
        CropForegroundd(keys=["image", "label"], source_key="image"),
        Orientationd(keys=["image", "label"], axcodes="RAS"),
        Spacingd(keys=["image", "label"], pixdim=(1.5, 1.5, 2.0), mode=("bilinear", "nearest")),
        RandCropByPosNegLabeld(
            keys=["image", "label"],
            label_key="label",
            spatial_size=(96, 96, 96),
            pos=1,
            neg=1,
            num_samples=4,
            image_key="image",
            image_threshold=0,
        ),
        ToTensord(keys=["image", "label"], device="cuda"),
        Affined(
            keys=['image', 'label'],
            affine=[],
            mode=('bilinear', 'nearest'),
            # .... add
        )
    ]
)
val_transforms = Compose(
    [
        EnsureChannelFirstd(keys=["image", "label"]),
        ScaleIntensityRanged(
            keys=["image"],
            a_min=-57,
            a_max=164,
            b_min=0.0,
            b_max=1.0,
            clip=True,
        ),
        CropForegroundd(keys=["image", "label"], source_key="image"),
        Orientationd(keys=["image", "label"], axcodes="RAS"),
        Spacingd(keys=["image", "label"], pixdim=(1.5, 1.5, 2.0), mode=("bilinear", "nearest")),
        ToTensord(keys=["image", "label"], device="cuda")
    ]
)

transforms_dict = {
    'train': train_transforms,
    'valid': val_transforms
}


class MRIDataset(Dataset):
    """
    Custom Dataset class for loading MRI images and masks with MONAI transformations.
    """

    def __init__(self, image_files, mask_files, mode: str):
        """
        Initialize the dataset by loading file paths and transformations.

        :param mode: Dataset split type ('train', 'valid')
        """
        self.transform = transforms_dict.get(mode)
        self.image_files = image_files
        self.mask_files = mask_files

    def __len__(self):
        # Return the number of images in the dataset.
        return len(self.image_files)

    def __getitem__(self, index):
        """
        Load an image and its corresponding mask, apply transformations.

        :param index: Index of the item to retrieve
        :return: Dictionary with transformed image and mask
        """
        img_names = (self.image_files[index], self.mask_files[index])
        img_and_mask = load_data_3D(img_names, early_stop=False)

        # Load image and segmentation
        data = {'img': img_and_mask[0], 'mask': img_and_mask[1]}
        data = self.transform(data)  # Apply transformations
        return data


def collate_batch(batch: Sequence):
    """
    Enhancement for PyTorch DataLoader default collate.
    If dataset already returns a list of batch data that generated in transforms, need to merge all data to 1 list.
    Then it's same as the default collate behavior.

    Note:
        Need to use this collate if apply some transforms that can generate batch data.

    """
    elem = batch[0]
    data = [i for k in batch for i in k] if isinstance(elem, list) else batch
    collate_fn = default_collate
    if isinstance(elem, Mapping):
        ret = {}
        for k in elem:
            key = k
            data_for_batch = [d[key] for d in data]
            ret[key] = collate_fn(data_for_batch)
    else:
        ret = collate_fn(data)
    return ret


def get_images():
    image_dir = "/home/groups/comp3710/HipMRI_Study_open/semantic_MRs"
    mask_dir = "/home/groups/comp3710/HipMRI_Study_open/semantic_labels_only"

    def extract_keys(file_path):
        parts = os.path.basename(file_path).split('_')
        return parts[0], str(parts[1])[-1]

    # List of image and mask filepaths
    image_files = [os.path.join(image_dir, fname) for fname in os.listdir(image_dir) if fname.endswith('.nii.gz')]
    mask_files = [os.path.join(mask_dir, fname) for fname in os.listdir(mask_dir) if fname.endswith('.nii.gz')]
    image_files, mask_files = sorted(image_files, key=extract_keys), sorted(mask_files, key=extract_keys)

    return np.array(image_files), np.array(mask_files)


def get_dataloaders(train_batch, val_batch) -> tuple[DataLoader, DataLoader, DataLoader]:
    image_files, mask_files = get_images()

    num_samples = len(image_files)
    np.random.seed(42)
    indices = np.random.permutation(num_samples)

    # Define split sizes (80% train, 10% val, 10% test)
    train_split = int(0.8 * num_samples)
    val_split = int(0.9 * num_samples)

    # use numpy advanced indexing (pass a list of indices)
    train_idx = indices[:train_split]
    val_idx = indices[train_split:val_split]
    test_idx = indices[val_split:]

    train_images, train_masks = image_files[train_idx], mask_files[train_idx]
    val_images, val_masks = image_files[val_idx], mask_files[val_idx]
    test_images, test_masks = image_files[test_idx], mask_files[test_idx]

    # get datasets
    train_ds = MRIDataset(train_images, train_masks, mode='train')
    val_ds = MRIDataset(val_images, val_masks, mode='valid')
    test_ds = MRIDataset(test_images, test_masks, mode='valid')

    # get dataloaders
    train_dataloader = DataLoader(train_ds, batch_size=train_batch, num_workers=4, pin_memory=True, shuffle=True,
                                  collate_fn=collate_batch)
    val_dataloader = DataLoader(val_ds, batch_size=val_batch, num_workers=4, pin_memory=True, shuffle=True,
                                collate_fn=collate_batch)
    test_dataloader = DataLoader(test_ds, batch_size=val_batch, num_workers=4, pin_memory=True, shuffle=True,
                                 collate_fn=collate_batch)

    return train_dataloader, val_dataloader, test_dataloader


def get_test_dataloader(batch_size):
    image_files, mask_files = get_images()
    num_samples = len(image_files)
    np.random.seed(42)
    indices = np.random.permutation(num_samples)

    split = int(0.9 * num_samples)
    test_idx = indices[split:]
    test_images, test_masks = image_files[test_idx], mask_files[test_idx]
    test_ds = MRIDataset(test_images, test_masks, mode='valid')
    test_dataloader = DataLoader(test_ds, batch_size=val_batch, num_workers=4, pin_memory=True, shuffle=True,
                                 collate_fn=collate_batch)
    return test_dataloader
