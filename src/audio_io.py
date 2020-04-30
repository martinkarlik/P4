import threading

import sofa
import sounddevice as sd
import numpy as np
import librosa
from scipy.signal import fftconvolve
from scipy.signal import *

signal, sampling_freq = librosa.load('../dependencies/impulse_responses/church_balcony.wav', sr=44100)
signal = np.reshape(signal, (-1, 1))
hrtf_database = sofa.Database.open('../dependencies/impulse_responses/QU_KEMAR_anechoic_1m.sofa')
ir_ear1 = hrtf_database.Data.IR.get_values(indices={"M": 1, "R": 0, "E": 0})
ir_ear2 = hrtf_database.Data.IR.get_values(indices={"M": 1, "R": 1, "E": 0})


class AudioIOThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.sampling_freq = 44100
        self.chunk_length = 0.05
        self.chunk_samples = int(self.sampling_freq * self.chunk_length)


class RecordingThread(AudioIOThread):

    def __init__(self):
        super().__init__()
        self.rec_data = np.array([[]])

        self.rec_stream = sd.InputStream(samplerate=self.sampling_freq, channels=2, blocksize=self.chunk_samples,
                                         callback=self.callback)

    def callback(self, indata, frames, time, status):

        if self.rec_data.size == 0:
            self.rec_data = indata
        else:
            self.rec_data = np.append(self.rec_data, indata, axis=0)

    def run(self):
        self.rec_stream.start()

    def stop(self):
        self.rec_stream.stop()
        self.rec_data = np.array(self.rec_data)

    def get_data(self):
        return self.rec_data


class PlaybackThread(AudioIOThread):

    def __init__(self):
        super().__init__()
        self.play_data = np.array([])
        self.positional_data = np.array([])

        self.filter_state_right = np.zeros(2047)
        self.filter_state_left = np.zeros(2047)
        self.filter_state_unknown = True

        self.chunk_index = 0

        sofa_0_5 = sofa.Database.open('../dependencies/impulse_responses/QU_KEMAR_anechoic_0_5m.sofa')
        sofa_1 = sofa.Database.open('../dependencies/impulse_responses/QU_KEMAR_anechoic_1m.sofa')
        sofa_2 = sofa.Database.open('../dependencies/impulse_responses/QU_KEMAR_anechoic_2m.sofa')
        sofa_3 = sofa.Database.open('../dependencies/impulse_responses/QU_KEMAR_anechoic_3m.sofa')

        self.hrtf_database = {0.2: sofa_0_5, 0.4: sofa_1, 0.8: sofa_2, 1.2: sofa_3}

        self.play_stream = sd.OutputStream(samplerate=self.sampling_freq, channels=2, blocksize=self.chunk_samples,
                                           callback=self.callback)
        self.done = False

    def run(self):
        self.play_stream.start()

    def callback(self, outdata, frames, time, status):

        corresponding_sample = self.chunk_index * frames + frames / 2

        elapsed_samples = self.positional_data[0][2]
        pos_index = 0
        while elapsed_samples < corresponding_sample:
            pos_index += 1
            elapsed_samples += self.positional_data[pos_index][2]

        angle = self.positional_data[pos_index][0]
        radius = self.positional_data[pos_index][1]

        start_index = self.chunk_index * frames
        end_index = (self.chunk_index + 1) * frames

        if angle == -1:  # don't apply any filters, output should stay stereo
            outdata[:, 0] = self.play_data[0, start_index:end_index]
            outdata[:, 1] = self.play_data[1, start_index:end_index]
            self.filter_state_unknown = True
        else:
            ir_ear_right = self.hrtf_database[radius].Data.IR.get_values(indices={"M": angle, "R": 0, "E": 0})
            ir_ear_left = self.hrtf_database[radius].Data.IR.get_values(indices={"M": angle, "R": 1, "E": 0})

            if self.filter_state_unknown:
                self.filter_state_right = np.zeros(2047)
                self.filter_state_left = np.zeros(2047)
                self.filter_state_unknown = False

            outdata[:, 0], self.filter_state_right = \
                lfilter(ir_ear_right, 1, self.play_data[0, start_index:end_index], zi=self.filter_state_right)
            outdata[:, 1], self.filter_state_left = \
                lfilter(ir_ear_left, 1, self.play_data[1, start_index:end_index], zi=self.filter_state_left)

        # outdata[:, 0] = self.play_data[0, start_index:end_index]
        # outdata[:, 1] = self.play_data[1, start_index:end_index]

        self.chunk_index += 1

        if self.chunk_index + 1 == len(self.play_data) / frames:
            self.play_stream.stop()
            self.done = True
            print("stopped")

    def set_data(self, play_data, positional_data=None, creator=True):

        self.play_data = play_data

        if not creator:
            self.positional_data = positional_data
