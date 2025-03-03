from typing import Callable, List, Optional

import cv2
from torchvision import transforms

from data import plot
from utils import constants, general_utils
from utils.training_helpers import *


def _loop_all(
    sample: List[Dict[str, np.ndarray]], sample_setup: Callable, f: Callable
) -> List[Dict[str, np.ndarray]]:
    for s in sample:
        process_sample, *args = sample_setup(s)
        if not process_sample:
            continue

        for key, value in s.items():
            s[key] = f(value, *args)

    return sample


def _process_all(s: Dict[str, np.ndarray]) -> Tuple[bool, None]:
    return True, None


class RandomHorizontalFlip:
    """RandomHorizontalFlip should be applied to all n images together, not just one

    """

    def __init__(self, probability: float = 0.5):
        self._probability = probability

    def __call__(
        self, sample: List[Dict[str, np.ndarray]]
    ) -> List[Dict[str, np.ndarray]]:
        if random.random() < self._probability:
            return _loop_all(sample, _process_all, self._f)
        else:
            return sample

    @staticmethod
    def _f(value: np.ndarray, *args) -> np.ndarray:
        return cv2.flip(value, flipCode=1)


class RandomRescale:
    def __init__(
        self, probability: float = 1 / 3, scales: Optional[List[float]] = None
    ):
        self._probability = probability
        if scales is None:
            scales = [1.1, 1.2]
        self._scales = scales

    def __call__(
        self, sample: List[Dict[str, np.ndarray]]
    ) -> List[Dict[str, np.ndarray]]:
        return _loop_all(sample, self._process_s, self._f)

    def _process_s(self, s: Dict[str, np.ndarray]) -> Tuple[bool, float]:
        return random.random() < self._probability, random.choice(self._scales)

    @staticmethod
    def _f(value: np.ndarray, *args) -> np.ndarray:
        scale = args[0]
        return cv2.resize(
            value, None, fx=scale, fy=scale, interpolation=constants.INTERPOLATION
        )


class RandomCrop:
    def __init__(
        self, probability: float = 1 / 3, scales: Optional[List[float]] = None
    ):
        self._probability = probability
        if scales is None:
            scales = [0.8, 0.9, 0.95]
        self._scales = scales

    def __call__(
        self, sample: List[Dict[str, np.ndarray]]
    ) -> List[Dict[str, np.ndarray]]:
        return _loop_all(sample, self._process_s, self._f)

    def _process_s(self, s: Dict[str, np.ndarray]) -> Tuple[bool, float, float]:
        scale = random.choice(self._scales)
        input_height, input_width, _ = s['image'].shape
        target_height, target_width = (
            int(input_height * scale),
            int(input_width * scale),
        )
        top = np.random.randint(0, input_height - target_height)
        left = np.random.randint(0, input_width - target_width)
        return (
            random.random() < self._probability,
            target_height,
            target_width,
            top,
            left,
        )

    @staticmethod
    def _f(value: np.ndarray, *args) -> np.ndarray:
        target_height, target_width, top, left = args
        return value[top : top + target_height, left : left + target_width]


class Resize:
    def __call__(
        self, sample: List[Dict[str, np.ndarray]]
    ) -> List[Dict[str, np.ndarray]]:
        return _loop_all(sample, _process_all, self._f)

    @staticmethod
    def _f(value: np.ndarray, *args) -> np.ndarray:
        # sometimes there's an assertion error if we use cv2 directly for the landmarks with cv2.INTER_AREA
        # this interpolation seems to be the best though for our use case
        # this might be because cv2 only cares about images, not general numpy arrays
        # https://github.com/opencv/opencv/issues/14770
        width, height, n_channels = value.shape
        if width == height == constants.IMSIZE:
            return value
        elif n_channels <= 3:
            return cv2.resize(
                value,
                (constants.IMSIZE, constants.IMSIZE),
                interpolation=constants.INTERPOLATION,
            )
        else:
            # this is faster than numpy indexing! tested with time measurements
            channel_list = []
            channels = cv2.split(value)
            for channel in channels:
                new_channel = cv2.resize(
                    channel,
                    (constants.IMSIZE, constants.IMSIZE),
                    interpolation=constants.INTERPOLATION,
                )
                channel_list.append(new_channel)
            return cv2.merge(channel_list)


class RescaleValues:
    def __call__(
        self, sample: List[Dict[str, np.ndarray]]
    ) -> List[Dict[str, np.ndarray]]:
        return _loop_all(sample, _process_all, self._f)

    @staticmethod
    def _f(value: np.ndarray, *args) -> np.ndarray:
        # don't rescale landmarks
        if value.shape[-1] == constants.DATASET_300VW_N_LANDMARKS:
            return value

        value = value.astype(float)
        value = (value / 255) * 2 - 1
        # assert -1 <= value.min() <= value.max() <= 1
        return value


class ChangeChannels:
    def __call__(
        self, sample: List[Dict[str, np.ndarray]]
    ) -> List[Dict[str, np.ndarray]]:
        return _loop_all(sample, _process_all, self._f)

    @staticmethod
    def _f(value: np.ndarray, *args) -> np.ndarray:
        # numpy image: H x W x C
        # torch image: C X H X W
        value = np.moveaxis(value, -1, 0)
        # assert value.shape == (
        #     constants.INPUT_CHANNELS,
        #     constants.IMSIZE,
        #     constants.IMSIZE,
        # ), f"wrong shape {image.shape}"
        return value


def _test_augmentations():
    from data.Dataset300VW import X300VWDataset

    dataset = X300VWDataset(constants.Dataset300VWMode.ALL, n_videos_limit=1)
    sample = dataset[0]

    image, landmarks = sample[0]['image'], sample[0]['landmarks']
    plot(image, landmarks_in_channel=landmarks, title='original')

    for t in (RandomHorizontalFlip, RandomRescale, RandomCrop):
        sample = t(probability=1)(sample)
        image, landmarks = sample[0]['image'], sample[0]['landmarks']
        plot(image, landmarks_in_channel=landmarks, title=t.__name__)

    transform = transforms.Compose(
        [
            RandomHorizontalFlip(probability=1),
            RandomRescale(probability=1),
            RandomCrop(probability=1),
            Resize(),
            RescaleValues(),
            ChangeChannels(),
        ]
    )
    sample = transform(sample)
    image, landmarks = sample[0]['image'], sample[0]['landmarks']
    image = general_utils.move_color_channel(image)
    image = general_utils.denormalize_picture(image)
    landmarks = general_utils.move_color_channel(landmarks)
    plot(image, landmarks_in_channel=landmarks, title='all')


def _test_values(batch_size: int = 32, n_videos_limit: Optional[int] = None) -> None:
    from torch.utils.data import DataLoader
    from tqdm import tqdm

    from data.Dataset300VW import X300VWDataset

    transform = transforms.Compose(
        [
            RandomHorizontalFlip(probability=1),
            RandomRescale(probability=1),
            RandomCrop(probability=1),
            Resize(),
            RescaleValues(),
            ChangeChannels(),
        ]
    )

    dataset = X300VWDataset(
        constants.Dataset300VWMode.ALL, transform=transform, n_videos_limit=None
    )
    dataloader = DataLoader(
        dataset, shuffle=False, batch_size=batch_size, num_workers=4, drop_last=False
    )
    for batch_index, batch in enumerate(tqdm(dataloader, desc='batch')):
        actual_batch_sizes = [sample['image'].shape[0] for sample in batch] + [
            sample['landmarks'].shape[0] for sample in batch
        ]
        assert len(set(actual_batch_sizes)) == 1

        image_target_shape = (
            actual_batch_sizes[0],
            constants.INPUT_CHANNELS,
            constants.IMSIZE,
            constants.IMSIZE,
        )
        landmarks_target_shape = (
            actual_batch_sizes[0],
            constants.DATASET_300VW_N_LANDMARKS,
            constants.IMSIZE,
            constants.IMSIZE,
        )
        for sample in tqdm(batch, desc='sample', leave=False):
            image, landmarks = sample['image'], sample['landmarks']

            assert (
                image.shape == image_target_shape
            ), f'image shape should be {image_target_shape} but is {image.shape}'
            assert torch.isfinite(image).all() and not torch.isnan(image).any()
            assert (image >= -1).all() and (image <= 1).all()

            assert (
                landmarks.shape == landmarks_target_shape
            ), f'landmarks shape should be {landmarks_target_shape} but is {landmarks.shape}'
            assert torch.isfinite(landmarks).all() and not torch.isnan(landmarks).any()
            # assert (landmarks >= -1).all() and (landmarks <= 1).all()


if __name__ == '__main__':
    _test_augmentations()
    # _test_values()
