# Lint as: python3
"""SHARK Tank"""
# python generate_sharktank.py, you have to give a csv tile with [model_name, model_download_url]
# will generate local shark tank folder like this:
#   /SHARK
#     /gen_shark_tank
#       /albert_lite_base
#       /...model_name...
#

import os
import csv
import argparse
from shark.shark_importer import SharkImporter
import subprocess as sp
import hashlib
import numpy as np
from pathlib import Path
from apps.stable_diffusion.src.models import (
    model_wrappers as mw,
)
from apps.stable_diffusion.src.utils.stable_args import (
    args,
)


def create_hash(file_name):
    with open(file_name, "rb") as f:
        file_hash = hashlib.blake2b()
        while chunk := f.read(2**20):
            file_hash.update(chunk)

    return file_hash.hexdigest()


def save_torch_model(torch_model_list):
    from tank.model_utils import (
        get_hf_model,
        get_hf_seq2seq_model,
        get_vision_model,
        get_hf_img_cls_model,
        get_fp16_model,
    )

    with open(torch_model_list) as csvfile:
        torch_reader = csv.reader(csvfile, delimiter=",")
        fields = next(torch_reader)
        for row in torch_reader:
            print(f"row {row}")
            torch_model_name = row[0]
            tracing_required = row[1]
            model_type = row[2]
            is_dynamic = row[3]

            tracing_required = False if tracing_required == "False" else True
            is_dynamic = False if is_dynamic == "False" else True

            model = None
            input = None
            if model_type == "stable_diffusion":
                args.use_tuned = False
                args.import_mlir = True
                args.use_tuned = False
                args.local_tank_cache = WORKDIR

                precision_values = ["fp16"]
                seq_lengths = [64, 77]
                for precision_value in precision_values:
                    args.precision = precision_value
                    for length in seq_lengths:
                        model = mw.SharkifyStableDiffusionModel(
                            model_id=torch_model_name,
                            custom_weights="",
                            precision=precision_value,
                            max_len=length,
                            width=512,
                            height=512,
                            use_base_vae=False,
                            debug=True,
                            sharktank_dir=WORKDIR,
                            generate_vmfb=False,
                        )
                        model()
                continue
            if model_type == "vision":
                model, input, _ = get_vision_model(torch_model_name)
            elif model_type == "hf":
                model, input, _ = get_hf_model(torch_model_name)
            elif model_type == "hf_seq2seq":
                model, input, _ = get_hf_seq2seq_model(torch_model_name)
            elif model_type == "hf_img_cls":
                model, input, _ = get_hf_img_cls_model(torch_model_name)
            elif model_type == "fp16":
                model, input, _ = get_fp16_model(torch_model_name)
            torch_model_name = torch_model_name.replace("/", "_")
            torch_model_dir = os.path.join(
                WORKDIR, str(torch_model_name) + "_torch"
            )
            os.makedirs(torch_model_dir, exist_ok=True)

            mlir_importer = SharkImporter(
                model,
                (input,),
                frontend="torch",
            )
            mlir_importer.import_debug(
                is_dynamic=False,
                tracing_required=tracing_required,
                dir=torch_model_dir,
                model_name=torch_model_name,
            )
            mlir_hash = create_hash(
                os.path.join(
                    torch_model_dir, torch_model_name + "_torch" + ".mlir"
                )
            )
            np.save(os.path.join(torch_model_dir, "hash"), np.array(mlir_hash))
            # Generate torch dynamic models.
            if is_dynamic:
                mlir_importer.import_debug(
                    is_dynamic=True,
                    tracing_required=tracing_required,
                    dir=torch_model_dir,
                    model_name=torch_model_name + "_dynamic",
                )


def save_tf_model(tf_model_list):
    from tank.model_utils_tf import (
        get_causal_image_model,
        get_causal_lm_model,
        get_keras_model,
        get_TFhf_model,
        get_tfhf_seq2seq_model,
    )
    import tensorflow as tf

    visible_default = tf.config.list_physical_devices("GPU")
    try:
        tf.config.set_visible_devices([], "GPU")
        visible_devices = tf.config.get_visible_devices()
        for device in visible_devices:
            assert device.device_type != "GPU"
    except:
        # Invalid device or cannot modify virtual devices once initialized.
        pass

    with open(tf_model_list) as csvfile:
        tf_reader = csv.reader(csvfile, delimiter=",")
        fields = next(tf_reader)
        for row in tf_reader:
            tf_model_name = row[0]
            model_type = row[1]

            model = None
            input = None
            print(f"Generating artifacts for model {tf_model_name}")
            if model_type == "hf":
                model, input, _ = get_causal_lm_model(tf_model_name)
            elif model_type == "img":
                model, input, _ = get_causal_image_model(tf_model_name)
            elif model_type == "keras":
                model, input, _ = get_keras_model(tf_model_name)
            elif model_type == "TFhf":
                model, input, _ = get_TFhf_model(tf_model_name)
            elif model_type == "tfhf_seq2seq":
                model, input, _ = get_tfhf_seq2seq_model(tf_model_name)

            tf_model_name = tf_model_name.replace("/", "_")
            tf_model_dir = os.path.join(WORKDIR, str(tf_model_name) + "_tf")
            os.makedirs(tf_model_dir, exist_ok=True)
            mlir_importer = SharkImporter(
                model,
                inputs=input,
                frontend="tf",
            )
            mlir_importer.import_debug(
                is_dynamic=False,
                dir=tf_model_dir,
                model_name=tf_model_name,
            )
            mlir_hash = create_hash(
                os.path.join(tf_model_dir, tf_model_name + "_tf" + ".mlir")
            )
            np.save(os.path.join(tf_model_dir, "hash"), np.array(mlir_hash))


def save_tflite_model(tflite_model_list):
    from shark.tflite_utils import TFLitePreprocessor

    with open(tflite_model_list) as csvfile:
        tflite_reader = csv.reader(csvfile, delimiter=",")
        for row in tflite_reader:
            print("\n")
            tflite_model_name = row[0]
            tflite_model_link = row[1]
            print("tflite_model_name", tflite_model_name)
            print("tflite_model_link", tflite_model_link)
            tflite_model_name_dir = os.path.join(
                WORKDIR, str(tflite_model_name) + "_tflite"
            )
            os.makedirs(tflite_model_name_dir, exist_ok=True)
            print(f"TMP_TFLITE_MODELNAME_DIR = {tflite_model_name_dir}")

            # Preprocess to get SharkImporter input args
            tflite_preprocessor = TFLitePreprocessor(str(tflite_model_name))
            raw_model_file_path = tflite_preprocessor.get_raw_model_file()
            inputs = tflite_preprocessor.get_inputs()
            tflite_interpreter = tflite_preprocessor.get_interpreter()

            # Use SharkImporter to get SharkInference input args
            my_shark_importer = SharkImporter(
                module=tflite_interpreter,
                inputs=inputs,
                frontend="tflite",
                raw_model_file=raw_model_file_path,
            )
            my_shark_importer.import_debug(
                dir=tflite_model_name_dir,
                model_name=tflite_model_name,
                func_name="main",
            )
            mlir_hash = create_hash(
                os.path.join(
                    tflite_model_name_dir,
                    tflite_model_name + "_tflite" + ".mlir",
                )
            )
            np.save(
                os.path.join(tflite_model_name_dir, "hash"),
                np.array(mlir_hash),
            )


# Validates whether the file is present or not.
def is_valid_file(arg):
    if not os.path.exists(arg):
        return None
    else:
        return arg


if __name__ == "__main__":
    # Note, all of these flags are overridden by the import of args from stable_args.py, flags are duplicated temporarily to preserve functionality
    # parser = argparse.ArgumentParser()
    # parser.add_argument(
    #    "--torch_model_csv",
    #    type=lambda x: is_valid_file(x),
    #    default="./tank/torch_model_list.csv",
    #    help="""Contains the file with torch_model name and args.
    #         Please see: https://github.com/nod-ai/SHARK/blob/main/tank/torch_model_list.csv""",
    # )
    # parser.add_argument(
    #    "--tf_model_csv",
    #    type=lambda x: is_valid_file(x),
    #    default="./tank/tf_model_list.csv",
    #    help="Contains the file with tf model name and args.",
    # )
    # parser.add_argument(
    #    "--tflite_model_csv",
    #    type=lambda x: is_valid_file(x),
    #    default="./tank/tflite/tflite_model_list.csv",
    #    help="Contains the file with tf model name and args.",
    # )
    # parser.add_argument(
    #    "--ci_tank_dir",
    #    type=bool,
    #    default=False,
    # )
    # parser.add_argument("--upload", type=bool, default=False)

    # old_args = parser.parse_args()

    home = str(Path.home())
    WORKDIR = os.path.join(os.path.dirname(__file__), "gen_shark_tank")
    torch_model_csv = os.path.join(
        os.path.dirname(__file__), "tank", "torch_model_list.csv"
    )
    tf_model_csv = os.path.join(
        os.path.dirname(__file__), "tank", "tf_model_list.csv"
    )
    #tflite_model_csv = os.path.join(
    #    os.path.dirname(__file__), "tank", "tflite", "tflite_model_list.csv"
    #)

    save_torch_model(torch_model_csv)
    save_tf_model(tf_model_csv)
    #save_tflite_model(tflite_model_csv)
