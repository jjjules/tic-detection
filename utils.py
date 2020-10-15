import cv2
import numpy as np
import torch
import datetime
from matplotlib import pyplot as plt
    
def write_video(filename, frames, width, height, fps, grayscale=False):
    if grayscale:
        writer = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*"MP4V"), fps, (width, height), 0)
    else:
        writer = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*"MP4V"), fps, (width, height))
    
    for frame in np.clip(np.around(frames), 0, 255).astype(np.uint8):
        writer.write(frame)
    writer.release()

def show_video(frames, imduration=int(1000/24.0)):
    for frame in frames:
        cv2.imshow('frame',frame)
        if cv2.waitKey(imduration) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()

def reconstruction_error(frames1, frames2):
    if frames1.shape != frames2.shape:
        return -1
    return np.sqrt(np.mean((frames1 - frames2)**2))

def crit(output, gt):
    return torch.sqrt(torch.mean((output - gt)**2))

def normalize_frames(frames, **kwargs):
    mean = kwargs['mean'] if 'mean' in kwargs else np.mean(frames)
    frames = frames - mean
    std  = kwargs['std'] if 'std' in kwargs else np.std(frames)
    frames = frames / std
    
    return frames

def plot(x, ys, **kwargs):
    if 'fontsize' in kwargs:
        plt.rcParams.update({'font.size': kwargs['fontsize']})
    else:
        plt.rcParams.update({'font.size': 12})
        
        
    if 'figsize' in kwargs:
        plt.figure(figsize=kwargs['figsize'])
    else:
        plt.figure(figsize=(15,10))
        
    if 'xlabel' in kwargs:
        plt.xlabel(kwargs['xlabel'])
    if 'ylabel' in kwargs:
        plt.ylabel(kwargs['ylabel'])
        
    if 'yrange' in kwargs:
        low, high = kwargs['yrange']
        plt.ylim(low, high)
    
    if 'bound_to_plot' in kwargs:
        epoch, max_error = kwargs['bound_to_plot']
        ys = list(filter(lambda x: max(x[epoch:]) < max_error, ys))
        
        
    if 'labels' in kwargs:
        for y, label in zip(ys, kwargs['labels']):
            plt.plot(x, y, label=label)
        plt.legend()
    else:
        for y in ys:
            plt.plot(x, y)

    if 'title' in kwargs:
        plt.title(kwargs['title'])

    plt.show()

def sec2string(sec):
    if sec <= 60:
        return round(sec, 2)
    secr = round(sec)
    
    return str(datetime.timedelta(seconds=secr)).strip("00:")
