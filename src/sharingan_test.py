from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import numpy as np
import argparse
import os
import inspect
import json
from sharingan_base import *

def processArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", help="path to folder containing images")
    parser.add_argument("--output_dir", required=True, help="where to put output files")
    parser.add_argument("--checkpoint", required=True, help="directory with checkpoint to use for testing")
    parser.add_argument("--max_steps", type=int, help="number of training steps (0 to disable)")
    parser.add_argument("--batch_size", type=int, default=1, help="number of images in batch")

    a = parser.parse_args()

    if not os.path.exists(a.output_dir):
        os.makedirs(a.output_dir)

    return a

def main():

    a = processArgs()

    examples = load_examples(input_dir=a.input_dir, batch_size=a.batch_size, is_training=False)
    print("examples count = %d" % examples.count)

    # inputs and targets are [batch_size, height, width, channels]
    model = create_model(examples.inputs, examples.targets)

    inputs = examples.inputs
    targets = examples.targets
    outputs = model.outputs

    with tf.name_scope("encode_images"):
        display_fetches = {
            "paths": examples.paths,
            "inputs": inputs,
            "targets": targets,
            "outputs": outputs,
        }

    with tf.name_scope("parameter_count"):
        parameter_count = tf.reduce_sum([tf.reduce_prod(tf.shape(v)) for v in tf.trainable_variables()])

    server = tf.train.Server.create_local_server()
    saver = tf.train.Saver()

    tensors_to_log = {
        "d_loss": "discriminator_loss/discrim_loss",
        "g_loss_GAN":"generator_loss/gen_loss_GAN",
        "g_loss_L1":"generator_loss/gen_loss_L1"
    }
    logging_hook = tf.train.LoggingTensorHook(tensors=tensors_to_log, every_n_iter=1)

    max_steps = a.max_steps
    if(max_steps is None):
        max_steps = examples.steps_per_epoch

    init_op=tf.group(tf.global_variables_initializer(), tf.local_variables_initializer())
    scaffold = tf.train.Scaffold(init_op)

    with tf.train.MonitoredTrainingSession(master=server.target,
                                       config=tf.ConfigProto(allow_soft_placement=True),
                                       is_chief=True,
                                       scaffold = scaffold) as sess:
        print("loading model from checkpoint")
        checkpoint = tf.train.latest_checkpoint(a.checkpoint)
        saver.restore(sess, checkpoint)

        coord = tf.train.Coordinator()

        threads = tf.train.start_queue_runners(sess=sess, coord=coord)
        try:
            counter = 0
            while not sess.should_stop():
                if(max_steps < counter):
                    break
                fetches = sess.run(display_fetches)
                save_images(a.output_dir, fetches, counter)
                counter = counter + 1
        except tf.errors.OutOfRangeError:
            print('Done training -- epoch limit reached')
        finally:
            coord.request_stop()
            coord.join(threads)

main()
