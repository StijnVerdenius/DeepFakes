import cProfile
import inspect
import io
import os
import pstats

import numpy as np

from utils.constants import *


def ensure_current_directory():
    """
    ensures we run from main directory even when we run testruns

    :return:
    """

    current_dir = os.getcwd()
    default_name = "DeepFakes"
    base_name = default_name if default_name in current_dir else "5204PRAI6Y-project-ai"
    os.chdir(current_dir.split(base_name )[0] + base_name + "/")



def setup_directories():
    stamp = DATA_MANAGER.stamp
    dirs = OUTPUT_DIRS
    for dir_to_be in dirs:
        DATA_MANAGER.create_dir(f"{stamp}/{dir_to_be}")


def save_codebase_of_run(arguments):
    directory = f"./{PREFIX_OUTPUT}/{DATA_MANAGER.stamp}/{CODE_DIR}"
    f = open(f"{directory}/arguments.txt", "w")
    f.write(str(arguments).replace(", ", "\n"))
    f.close()

    stack = ["."]

    while len(stack) > 0:

        path = stack.pop(0)

        for file_name in os.listdir(os.path.join(os.getcwd(), path)):

            if file_name.endswith(".py"):
                f = open(f"{directory}/{file_name}".replace(".py", ""), "w")
                lines = open(f"{path}/{file_name}", "r").read()
                f.write(str(lines))
                f.close()
            elif (os.path.isdir(os.path.join(os.getcwd(), path, file_name))):
                stack.append(os.path.join(path, file_name))

    base = os.path.join(os.getcwd(), PREFIX_OUTPUT, DATA_MANAGER.stamp, CODE_DIR)
    for file_name in list(os.listdir(base)):
        if ("arguments.txt" in file_name): continue
        os.rename(base + "/" + file_name, base + "/" + file_name + ".py")


def assert_type(expectedType, content):
    """ makes sure type is respected"""

    func = inspect.stack()[1][3]
    assert isinstance(content, expectedType), "No {} entered in {} but instead value {}".format(str(expectedType), func,
                                                                                                str(content))


def assert_non_empty(content):
    """ makes sure not None or len()==0 """

    func = inspect.stack()[1][3]
    assert not content == None, "Content is null in {}".format(func)
    if (type(content) is list or type(content) == str):
        assert len(content) > 0, "Empty {} in {}".format(type(content), func)


def mean(input_list):
    assert_type(list, input_list)
    return sum(input_list) / len(input_list)


def start_timing():
    pr = cProfile.Profile()
    pr.enable()
    return pr


def stop_timing(pr):
    pr.disable()
    s = io.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats()
    print(s.getvalue())


def denormalize_picture(image: np.ndarray, binarised: bool = False) -> np.ndarray:
    """ denormalises picture for plotting """

    image = ((image + 1) / 2) * 255

    image[image > 255] = 255
    image = image.astype('uint8')

    if (binarised):
        image[image == 127] = 255

    return image


def de_torch(img):
    """ converts pytorch picture to numpy for plotting"""

    return move_color_channel(img.detach().cpu().numpy())


def move_color_channel(image: np.ndarray) -> np.ndarray:
    return np.moveaxis(image, 0, -1)


def BGR2RGB_numpy(image: np.ndarray) -> np.ndarray:
    # for some reason,
    # image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    # throws an error but the code below achieves the same thing
    temp = np.empty_like(image)
    temp[:, :, 0] = image[:, :, 2]
    temp[:, :, 1] = image[:, :, 1]
    temp[:, :, 2] = image[:, :, 0]
    return temp


def BGR2RGB_pytorch(images: torch.Tensor) -> torch.Tensor:
    temp = torch.empty_like(images)
    temp[:, 0, :, :] = images[:, 2, :, :]
    temp[:, 1, :, :] = images[:, 1, :, :]
    temp[:, 2, :, :] = images[:, 0, :, :]
    return temp


def get_generator_loss_weights(arguments):
    """ returns a dictionary with the right loss weights given parsed arguments """

    default_returnvalue = {key: value for key, value in arguments.__dict__.items() if
                           (("weight" in key) and (not value == -1))}
    if (not arguments.loss_gen == TOTAL_LOSS):
        for key in default_returnvalue:
            if (not arguments.loss_gen in key):
                default_returnvalue[key] = 0.0
    return default_returnvalue
