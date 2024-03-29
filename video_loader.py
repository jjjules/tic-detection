import numpy as np
import torch
import cv2

class VideoLoader:
    """
    A class used to easily manipulate and iterate over videos
    
    
    Args:
        filename (str):
            the filename of the video
        start (str):
            when to start reading the video file in seconds (default: 0)
        start_frame (int):
            the frame where to start reading the video file (default: 0)
        duration (float):
            the duration of the video in seconds (default: np.inf (i.e. entire video file))
        duration_frames (int):
            the number of frames in the video (default: np.inf (i.e. all frames in video file))
        gray (bool):
            if true map the frames to gray scale (default: False)
        scale (int, int):
            if not None, specify the resolution of each frame returned (default: None)
        torch (bool):
            if true return a torch.Tensor, otherwise a numpy.ndarray (default: True)
        sample_shape (list of ints):
            the shape of each frame in the object returned by the iterator (default: None)
        batch_size (int):
            the number of frames per batch in the iterator (default: 64)
        skip_frame (int):
            how many frames to skip when iterating over batches (default: 0)
        randit (int):
            if true sample the frames in the video in a random order (default: False)
        stride (int):
            the stride of the iterator (default: batch_size (non-overlapping))
        iterator_next_frame (bool):
            if true, return the batch as (batch[:-1], batch[-1]) (useful when having to 
            predict the next frame using all the batch) (default: False)
    
    """
    def __init__(self, filename, start=0, start_frame=0, duration=np.inf, duration_frames=np.inf, batch_size=64, gray=False, scale=None, skip_frame=0, randit=False,
                 torch=True, stride=None, sample_shape=None, iterator_next_frame=None):
        self.filename = filename
        self.gray = gray
        self.batch_size = batch_size
        cap = cv2.VideoCapture(filename)
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = round(cap.get(cv2.CAP_PROP_FPS))
        self.start = start
        self.start_frame = np.ceil(start*self.fps/batch_size)*batch_size
        if start_frame != 0:
            self.start_frame = start_frame
            self.start = start_frame/self.fps
        self.duration_frames = min((self.total_frames//batch_size)*batch_size, np.ceil(duration*self.fps/batch_size)*batch_size)
        self.duration = self.duration_frames/self.fps
        if duration_frames != np.inf:
            self.duration_frames = duration_frames
            self.duration = self.duration_frames/self.fps

        # Fix as frame number may exceed the video. Example: last gesture of Suturing_B001_capture1.avi
        self.duration_frames = int(min(self.total_frames-self.start_frame, self.duration_frames))
        self.width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if scale:
            self.scale = True
            self.original_width  = self.width
            self.original_height = self.height
            self.width, self.height = scale
        else:
            self.scale = False
        self.skip_frame = int(skip_frame)
        self.randit = randit
        self.torch = torch
        if stride is None:
            stride = batch_size
        else:
            if int(self.batch_size) % stride != 0:
                raise Exception("The stride must be a divisor of the batch size.")
        self.iterator_stride = stride
        self.sample_shape = sample_shape
        self.iterator_next_frame = iterator_next_frame

    def reduce_latent(self, model, trans=True):
        self.randit = self.skip_frame = 0

        reconstructed_frames = []
        for frames in self:
            # WILL ALWAYS BE TRANSFORM -> INV_TRANSFORM
            if trans:
                if self.torch:
                    reconstructed_frames.append(model.decode(*model.encode(frames)).detach())
                else:
                    reconstructed_frames.append(model.decode(*model.encode(frames)))
            else:
                reconstructed_frames.append(model(frames).detach())

        if self.torch:
            reconstructed_frames = torch.cat(reconstructed_frames, 0)
        else:
            reconstructed_frames = np.vstack(reconstructed_frames)
        return reconstructed_frames

    def get_all_frames(self, allow_skip=False, batch_multiple=False):
        frames = []
        cap = cv2.VideoCapture(self.filename)
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)
        current_frame = 0
        while cap.isOpened():
            ret, frame = cap.read()
            try:
                if allow_skip == True:
                    for _ in range(self.skip_frame):
                            ret, _ = cap.read()
                            current_frame += 1
                            if not ret:
                                raise StopIteration
            except StopIteration:
                self.__stop = True
                break
            if current_frame >= self.duration_frames:
                cap.release()
                break
            if ret:
                frames.append(self.frame_transform(frame))
                current_frame += 1
            else:
                cap.release()

        if self.sample_shape is not None:
            frames = np.reshape(frames, (-1, *self.sample_shape))
        return self.__from_frame_list(frames)

    def get_random_frames(self, frames_ratio, seed=42):
        nframes = int(self.duration_frames * frames_ratio)
        frames = []
        cap = cv2.VideoCapture(self.filename)
        np.random.seed(seed)
        frame_ids = np.random.choice(np.arange(self.duration_frames),
                                     size=nframes,
                                     replace=False, )
        while cap.isOpened():
            ret, frame = cap.read()
            current_frame = cap.get(cv2.CAP_PROP_POS_FRAMES)
            if ret:
                if current_frame in frame_ids:
                    frames.append(self.frame_transform(frame))
            else:
                cap.release()

        return self.__from_frame_list(frames)


    def frame_transform(self, frame):
        if self.scale:
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
        if self.gray:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        return frame

    def __from_frame_list(self, frames):
        if self.torch:
            frames = torch.FloatTensor(frames)
        else:
            frames = np.array(frames).astype(np.float32)

        return frames

    def __iter__(self):
        self.__cap = cv2.VideoCapture(self.filename)
        self.__frame_count = 0
        self.__frame_order = np.arange(self.start_frame, self.start_frame+self.duration_frames)
        if self.randit:
            np.random.shuffle(self.__frame_order)
        self.__frame_order = iter(self.__frame_order)
        self.last_frames = []
        self.__stop = False
        return self

    def __next__(self):
        frames_position = []
        if self.__stop:
            raise StopIteration()

        frames = self.last_frames[self.iterator_stride:]
        while self.__cap.isOpened():
            try:
                next_frame = next(self.__frame_order)
                frames_position.append(next_frame)
                self.__cap.set(cv2.CAP_PROP_POS_FRAMES, next_frame)
                for _ in range(self.skip_frame):
                    next(self.__frame_order)
            except StopIteration:
                self.__stop = True
                break
            ret, frame = self.__cap.read()

            if ret:
                frames.append(self.frame_transform(frame))
                self.__frame_count += 1
            else:
                self.__cap.release()
                self.__stop = True
                break

            if len(frames) % self.batch_size == 0:
                break

        self.last_frames = frames
        if self.__frame_count*(self.skip_frame+1) >= self.duration_frames:
            self.__stop = True

        if self.iterator_next_frame:
            frames, next_frame = frames[:-1], frames[-1]
        if self.sample_shape is not None:
            frames = np.reshape(frames, (-1, *self.sample_shape))

        if self.iterator_next_frame:
            return self.__from_frame_list(frames), next_frame
        else:
            return self.__from_frame_list(frames)

    def write(self, filename):
        last_torch = self.torch
        self.torch = False

        if self.gray:
            writer = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*"MP4V"), self.fps, (self.width, self.height), 0)
        else:
            writer = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*"MP4V"), self.fps, (self.width, self.height))

        cap = cv2.VideoCapture(self.filename)
        current_frame = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if current_frame >= self.duration_frames:
                cap.release()
                break
            if ret:
                #print(frame.shape)
                frame = self.frame_transform(frame)
                #print(frame.shape)
                writer.write(frame)
                current_frame += 1
            else:
                cap.release()

        writer.release()
        self.torch = last_torch
