import sofa
import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import *
import threading

from Source import interface
from Source import audio_processing


class RecordingThread(threading.Thread):

    def __init__(self, thread_id):
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.keep_on = True
        self.mic_data = np.array([])
        self.sampling_freq = 48000
        self.rec_time = 5  # seconds
        sd.default.samplerate = self.sampling_freq
        sd.default.channels = (1, 2)

    def run(self):
        while self.keep_on:
            print("Recording new chunk.")
            current_chunk = sd.rec(self.rec_time * self.sampling_freq)
            sd.wait()
            if self.mic_data.size == 0:
                self.mic_data = current_chunk
            else:
                self.mic_data = np.append(self.mic_data, current_chunk)

    def play(self):
        print(self.mic_data.shape)
        sd.play(self.mic_data, self.sampling_freq)
        sd.wait()

    def get_data(self):
        return self.mic_data


interface = interface.CreatorInterface()
recording = RecordingThread(1)

while interface.running:
    interface.update()

    if interface.audio_manager.recording_state["started"]:
        recording.start()

    if interface.audio_manager.recording_state["in_process"]:
        pass

    elif interface.audio_manager.recording_state["stopped"]:
        recording.keep_on = False
        recording.join()

        rec_data = recording.get_data()
        audio_data = interface.audio_controller.full_audio_data

        audio_data = np.array(audio_data)

        total_frames = np.sum(audio_data[:, 1])
        audio_data[:, 1] = np.divide(audio_data[:, 1], total_frames)

        for sample in audio_data:
            sample[1] = int(sample[1] * len(rec_data))

        audio_data[len(audio_data) - 1][1] += abs(len(rec_data) - np.sum(audio_data[:, 1]))

        reverb_data = audio_processing.remove_redundant_reverb(audio_data)

        output = []
        elapsed_duration = 0
        for sample in reverb_data:
            start_index = elapsed_duration
            elapsed_duration += sample[1]
            end_index = elapsed_duration

            result = audio_processing.add_reverb(rec_data[start_index:end_index], recording.sampling_freq, sample[0])
            output.append(result)

        # sd.play(output)
        # sd.wait()


        # tmp_reverb_signal = audio_processing.add_reverb(rec_data, recording.sampling_freq, interface.audio_controller.current_audio_data)
    # if interface.audio_manager.playback_started:
    #     recording.play()


# TODO Listener Interface
# TODO Continues recording of flexible length (stopped when told to do so)