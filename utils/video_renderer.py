import numpy as np
import cv2
import torch
import torch.multiprocessing as mp
from fsgan.utils.img_utils import tensor2bgr
from fsgan.utils.bbox_utils import crop2img, scale_bbox

class Task():
    # for excuting tasks that can be put on input_queue
    def __init__(self, cmd, data=None):
        self.cmd = cmd
        self.data = data

class VideoRenderer(mp.Process):
    """ Renders input video frames to both screen and video file.

    For more control on the rendering, this class should be inherited from and the on_render method overridden
    with an application specific implementation.

    Args:
        display (bool): If True, the rendered video will be displayed on screen
        verbose (int): Verbose level. Controls the amount of debug information in the rendering
        verbose_size (tuple of int): The rendered frame size for verbose level other than zero (width, height)
        output_crop (bool): If True, a cropped frame of size (resolution, resolution) will be rendered for
            verbose level zero
        resolution (int): Determines the size of cropped frames to be (resolution, resolution)
        crop_scale (float): Multiplier factor to scale tight bounding boxes
        encoder_codec (str): Encoder codec code
        separate_process (bool): If True, the renderer will be run in a separate process
    """
    def __init__(self, display=False, verbose=0, verbose_size=None, output_crop=False, resolution=256, crop_scale=1.2,
                 encoder_codec='avc1', separate_process=False):
        super(VideoRenderer, self).__init__()
        self._display = display
        self._verbose = verbose
        self._verbose_size = verbose_size
        self._output_crop = output_crop
        self._resolution = resolution
        self._crop_scale = crop_scale
        self._running = True
        self._input_queue = mp.Queue()
        self._reply_queue = mp.Queue()
        print('about to init VideoWrite_fourcc with:', encoder_codec)
        self._fourcc = cv2.VideoWriter_fourcc(*encoder_codec)
        self._separate_process = separate_process
        self._in_vid = None
        self._out_vid = None
        self._seq = None
        self._in_vid_path = None
        self._out_vid_path = None
        self._total_frames = None
        self._frame_count = 0

    def init(self, in_vid_path, seq, out_vid_path=None, **kwargs):
        """ Initialize the video render for a new video rendering job.
            Actual work done by _init_task.
            Work included copying all the frames up to the first segment.

        Args:
            in_vid_path (str): Input video path
            seq (Sequence): Input sequence corresponding to the input video
            out_vid_path (str, optional): If specified, the rendering will be written to an output video in that path
            **kwargs (dict): Additional keyword arguments that will be added as members of the class. This allows
                inheriting classes to access those arguments from the new process
        """
        self.execute_task('init', [in_vid_path, seq, out_vid_path, kwargs])
        # remove the code that write out the first frames:
        #self.write_frames(seq.start_index)

    def write_frames(self, count):
        """ Writes frames from target video to output
            Intended for frames with no faces
        """
        self.execute_task('write_frames', count)

    def write(self, tgt_seq, seq_index, *args):
        """ Add tensors for rendering.
            Actual work done by _write_batch.

        Args:
            *args (tuple of torch.Tensor): The tensors for rendering
        """
        self.execute_task('write', [tgt_seq, seq_index, [a.cpu() for a in args]])

    def finalize(self):
        # Copies frames that are after the sequence
        # Actual work done by _finalize_task
        self.execute_task('finalize')

    def wait_until_finished(self):
        """ Wait for the video renderer to finish the current video rendering job. """
        if self._separate_process:
            return self._reply_queue.get()
        else:
            return True

    def on_render(self, *args):
        """ Given the input tensors this method produces a cropped rendered image.

        This method should be overridden by inheriting classes to customize the rendering. By default this method
        expects the first tensor to be a cropped image tensor of shape (B, 3, H, W) where B is the batch size,
        H is the height of the image and W is the width of the image.

        Args:
            *args (tuple of torch.Tensor): The tensors for rendering

        Returns:
            render_bgr (np.array): The cropped rendered image
        """
        return tensor2bgr(args[0])

    def start(self):
        if self._separate_process:
            super(VideoRenderer, self).start()

    def kill(self):
        if self._separate_process:
            super(VideoRenderer, self).kill()

    def run(self):
        """ Main processing loop. Intended to be executed on a separate process. """
        while self._running:
            task = self._input_queue.get()

            if isinstance(task, Task):
                self._run_task(task.command, task.data)
                if task.command == "finalize":
                    self._reply_queue.put(True)
                continue

            # None of this should be called anymore
            assert False, 'use new task system'


            """ OLD RUN CODE
            # Initialize new video rendering task
            # "init" task
            if self._in_vid is None:
                self._init_task(*task[:3], task[3])
                continue

            # Finalize task
            # "finalize" task
            if isinstance(task, bool):
                self._finalize_task()

                # Notify job is finished
                self._reply_queue.put(True)
                continue

            # Write a batch of frames
            # "write" task
            self._write_batch(task)
            """

    def execute_task(self, command, data=None):
        if self._separate_process:
            self._input_queue.put(Task(command, data))
        else:
            self._run_task(command, data)

    def _run_task(self, command, data):
        # print('_run_task:', command)
        if command == "init":
            # expand from self.execute_task('init', [in_vid_path, seq, out_vid_path, kwargs])
            self._init_task(*data[:3], data[3])
        elif command == "write_frames":
            self._write_frames(data)
        elif command == "write":
            self._write_batch(data)
        elif command == "finalize":
            self._finalize_task()
        else:
            assert False, f'Unknown command: {command}'


    def _render(self, render_bgr, full_frame_bgr=None, bbox=None):
        if self._verbose == 0 and not self._output_crop and full_frame_bgr is not None:
            render_bgr = crop2img(full_frame_bgr, render_bgr, bbox)
        if self._out_vid_path is not None:
            # this is a bit of a hack... but if only one frame write out PNG file
            if self._total_frames == 1:
                image_path = self._out_vid_path.replace('.mp4', '.png')
                cv2.imwrite(image_path, render_bgr)
            else:
                # write frame to video
                self._out_vid.write(render_bgr)
        if self._display:
            cv2.imshow('render', render_bgr)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self._running = False

    def _init_task(self, in_vid_path, seq, out_vid_path, additional_attributes):
        print('video_renderer._init_task start, out_vid_path:', out_vid_path)
        self._in_vid_path, self._seq = in_vid_path, seq
        self._out_vid_path = out_vid_path
        self._frame_count = 0

        # Add additional arguments as members
        for attr_name, attr_val in additional_attributes.items():
            setattr(self, attr_name, attr_val)

        # Open input video
        self._in_vid = cv2.VideoCapture(self._in_vid_path)
        assert self._in_vid.isOpened(), f'Failed to open video: "{self._in_vid_path}"'

        in_total_frames = int(self._in_vid.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self._in_vid.get(cv2.CAP_PROP_FPS)
        in_vid_width = int(self._in_vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        in_vid_height = int(self._in_vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._total_frames = in_total_frames if self._verbose == 0 else len(self._seq)
        print(f'Debug: initializing video: "{self._in_vid_path}", total_frames={self._total_frames}')

        # Initialize output video
        if self._out_vid_path is not None:
            out_size = (in_vid_width, in_vid_height)
            if self._verbose <= 0 and self._output_crop:
                out_size = (self._resolution, self._resolution)
            elif self._verbose_size is not None:
                out_size = self._verbose_size
            if in_total_frames > 1:
                self._out_vid = cv2.VideoWriter(self._out_vid_path, self._fourcc, fps, out_size)


    def _write_frames(self, frame_count):
        # E.g. Write frames as they are until the start of the sequence
        if self._verbose == 0:
            print(f'Debug: render {frame_count} frames (outside of seq)')
            for i in range(frame_count):
                # Read frame
                ret, frame_bgr = self._in_vid.read()
                assert frame_bgr is not None, f'Failed to read frame {self._frame_count + i} from input video: "{self._in_vid_path}"'
                self._render(frame_bgr)
                self._frame_count += 1

    def _write_batch(self, seq_and_tensors):
        seq = seq_and_tensors[0]
        batch_index = seq_and_tensors[1]
        tensors = seq_and_tensors[2]
        batch_size = tensors[0].shape[0]
        #print(f'Debug: _write_batch, size is {batch_size}')

        # For each frame in the current batch of tensors
        for b in range(batch_size):
            # Handle full frames if output_crop was not specified
            full_frame_bgr, bbox = None, None
            if self._verbose == 0 and not self._output_crop:
                # Read frame from input video
                ret, full_frame_bgr = self._in_vid.read()
                assert full_frame_bgr is not None, \
                    f'Failed to read frame {self._frame_count} from input video: "{self._in_vid_path}"'

                # Get bounding box from sequence
                # print(dir(seq))
                #print(f'get bounding box {b}... batch_index={batch_index} seq.start_index={seq.start_index} seq.detections={len(seq.detections)} frame_count={self._frame_count}')
                det = seq[batch_index + b]
                bbox = np.concatenate((det[:2], det[2:] - det[:2]))
                bbox = scale_bbox(bbox, self._crop_scale)

            render_bgr = self.on_render(*[t[b] for t in tensors])
            #print('render bbox:', bbox)
            #cv2.imwrite('./5-render_bgr.png', render_bgr)
            #cv2.imwrite('./5-full_frame_bgr.png', full_frame_bgr)
            self._render(render_bgr, full_frame_bgr, bbox)
            self._frame_count += 1
            # print(f'Debug: Wrote frame: {self._frame_count}')

    def _finalize_task(self):
        # copy over all frames after the seq
        #if self._verbose == 0 and self._frame_count >= (self._seq.start_index + len(self._seq)):
        #    print(f'Debug: Write frames after seq starting at {self._seq.start_index + len(self._seq)} until {self._total_frames} frames')
        #    for i in range(self._seq.start_index + len(self._seq), self._total_frames):
        #        # Read frame
        #        ret, frame_bgr = self._in_vid.read()
        #        assert frame_bgr is not None, f'Failed to read frame {i} from input video: "{self._in_vid_path}"'
        #        self._render(frame_bgr)
        #        self._frame_count += 1
        #        # print(f'Debug: Wrote frame: {self._frame_count}')
        #print(f'Debug: Wrote up to {self._frame_count} of total {self._total_frames}')
        #
        # if self._frame_count >= self._total_frames:
        # Clean up
        self._in_vid.release()
        self._out_vid != None and self._out_vid.release()
        self._in_vid = None
        self._out_vid = None
        self._seq = None
        self._in_vid_path = None
        self._total_frames = None
        self._frame_count = 0
