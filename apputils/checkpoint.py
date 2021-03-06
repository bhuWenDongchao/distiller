#
# Copyright (c) 2018 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

""" Helper code for checkpointing models, with support for saving the pruning schedule.

Adding the schedule information in the model checkpoint is helpful in resuming
a pruning session, or for querying the pruning schedule of a sparse model.
"""

import os
import shutil
import logging
import torch
import distiller
msglogger = logging.getLogger()


def save_checkpoint(epoch, arch, model, optimizer, scheduler=None, best_top1=None, is_best=False, name=None):
    """Save a pytorch training checkpoint

    Args:
        epoch: current epoch
        arch: name of the network arechitecture/topology
        model: a pytorch model
        optimizer: the optimizer used in the training session
        scheduler: the CompressionScheduler instance used for training, if any
        best_top1: the best top1 score seen so far
        is_best: True if this is the best (top1 accuracy) model so far
        name: the name of the checkpoint file
    """
    msglogger.info("Saving checkpoint")
    filename = 'checkpoint.pth.tar' if name is None else name + '_checkpoint.pth.tar'
    filename_best = 'best.pth.tar' if name is None else name + '_best.pth.tar'
    checkpoint = {}
    checkpoint['epoch'] = epoch
    checkpoint['arch'] =  arch
    checkpoint['state_dict'] = model.state_dict()
    if best_top1 is not None:
        checkpoint['best_top1'] = best_top1
    checkpoint['optimizer'] = optimizer.state_dict()
    if scheduler is not None:
        checkpoint['compression_sched'] = scheduler.state_dict()
    if hasattr(model, 'thinning_recipe'):
        checkpoint['thinning_recipe'] = model.thinning_recipe

    torch.save(checkpoint, filename)
    if is_best:
        shutil.copyfile(filename, filename_best)


def load_checkpoint(model, chkpt_file, optimizer=None):
    """Load a pytorch training checkpoint

    Args:
        model: the pytorch model to which we will load the parameters
        chkpt_file: the checkpoint file
        optimizer: the optimizer to which we will load the serialized state
    """
    compression_scheduler = None
    start_epoch = 0

    if os.path.isfile(chkpt_file):
        msglogger.info("=> loading checkpoint %s", chkpt_file)
        checkpoint = torch.load(chkpt_file)
        start_epoch = checkpoint['epoch'] + 1
        best_top1 = checkpoint.get('best_top1', None)
        if best_top1 is not None:
            msglogger.info("   best top@1: %.3f", best_top1)

        if 'compression_sched' in checkpoint:
            compression_scheduler = distiller.CompressionScheduler(model)
            compression_scheduler.load_state_dict(checkpoint['compression_sched'])
            msglogger.info("Loaded compression schedule from checkpoint (epoch %d)",
                           checkpoint['epoch'])

            if 'thinning_recipe' in checkpoint:
                msglogger.info("Loaded a thinning recipe from the checkpoint")
                distiller.execute_thinning_recipe(model,
                                                  compression_scheduler.zeros_mask_dict,
                                                  checkpoint['thinning_recipe'])
        else:
            msglogger.info("Warning: compression schedule data does not exist in the checkpoint")
            msglogger.info("=> loaded checkpoint '%s' (epoch %d)",
                           chkpt_file, checkpoint['epoch'])

        model.load_state_dict(checkpoint['state_dict'])

        return model, compression_scheduler, start_epoch
    else:
        msglogger.info("Error: no checkpoint found at %s", chkpt_file)
        exit(1)
