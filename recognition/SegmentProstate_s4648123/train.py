import os
import time

import numpy as np
import torch
from utils import one_hot_mask
from dataset import get_dataloaders
from modules import UNet3D

MODEL_PATH = "best_unet.pth"


class Dice(torch.nn.Module):
    def __init__(self, smooth=1e-6):
        """
        Initialize the Dice loss module.

        Args:
            smooth (float): Smoothing factor to avoid division by zero when calculating the Dice coefficient.
        """
        super(Dice, self).__init__()
        self.smooth = smooth

    def dice(self, pred, target):
        """
        Compute the Dice coefficient between 3D predictions and targets.

        Args:
            pred (torch.Tensor): Model predictions with shape (batch_size, num_classes, depth, height, width).
            target (torch.Tensor): Ground truth with shape (batch_size, 1, depth, height, width).

        Returns:
            torch.Tensor: Dice coefficients for each class.
        """
        # Apply softmax to logits to get probabilities
        input = torch.softmax(pred, dim=1)  # (B, C, D, H, W)

        # Convert target to one-hot encoding along the class dimension
        target = one_hot_mask(target)  # (B, C, D, H, W)

        # Define the axes for reduction (batch, depth, height, width)
        reduce_axis = [0] + list(range(2, len(input.shape)))  # [0, 2, 3, 4]

        # Compute the intersection and union for each class
        intersection = torch.sum(input * target, dim=reduce_axis)  # (num_classes,)
        ground_o = torch.sum(target, dim=reduce_axis)  # (num_classes,)
        pred_o = torch.sum(input, dim=reduce_axis)  # (num_classes,)

        # Compute the denominator for Dice coefficient
        denominator = ground_o + pred_o

        # Compute Dice coefficient for each class
        f = (2.0 * intersection + self.smooth) / (denominator + self.smooth)

        return f

    def forward(self, logits, target):
        """
        Compute the Dice loss.

        Args:
            logits (Tensor): Model outputs with shape (batch_size, num_classes, height, width).
            target (Tensor): Ground truth with shape (batch_size, 1, height, width).

        Returns:
            Tensor: Dice loss.
        """
        coeff = self.dice(logits, target)  # Compute Dice coefficient
        dice_loss = 1 - torch.mean(coeff)  # Mean over classes

        return dice_loss


def train():
    pass
    # TODO: Build train function


def validate():
    pass
    # TODO: Build validate function


if __name__ == '__main__':
    """
    Main function to run the training and validation processes.
    """
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    # Set up datasets and DataLoaders
    batch_size = 8
    train_loader, val_loader, test_loader = get_dataloaders(train_batch=batch_size, val_batch=batch_size)

    # Initialize model
    unet = UNet3D()
    unet = unet.to(device)

    epochs = 15
    criterion = Dice()
    # TODO: find best optimizer for UNet3D for my images
    # optimizer =

    best_metric = float(0.)
    best_state = unet.state_dict()

    train_start_time = time.time()

    # Training and evaluation loop
    for epoch in range(epochs):
        epoch_loss = train()
        print(f"Train Epoch {epoch + 1}/{epochs}, Training Loss: {epoch_loss / len(train_loader):.4f}")

        # TODO: Build validate function

        dice_score = validate()
        dice_coeff_str = ', '.join([f"{dc:.2f}" for dc in dice_score])
        print(f"Test Epoch {epoch + 1}/{epochs}, Dice Coefficients for each class: [{dice_coeff_str}]")

        avg_dice_score = float(np.mean(dice_score))
        if avg_dice_score > best_metric:
            best_metric = avg_dice_score
            best_state = unet.state_dict()
            # Save the best model state
            torch.save(best_state, MODEL_PATH)

    train_end_time = time.time()  # End timer
    train_time = train_end_time - train_start_time  # Calculate elapsed time
    print(f"Total training time: {train_time:.2f} seconds")

    # Load the best model state (if not loaded already)
    unet.load_state_dict(torch.load(MODEL_PATH, weights_only=True))

    # test the model on seperate test dataset
    test_start_time = time.time()  # Start timer
    final_dice_score = validate()

    test_end_time = time.time()  # End timer
    test_time = test_end_time - test_start_time  # Calculate elapsed time
    dice_coeff_str = ', '.join([f"{dc:.2f}" for dc in final_dice_score])
    print(f"Final Dice Coefficients for each class: [{dice_coeff_str}]")
    print(f"Total test time: {test_time:.2f} seconds")
