'''
Author:     Ji-Sung Kim
Project:    deepjazz
Purpose:    Parse, cleanup and process data.

Code adapted from Evan Chow's jazzml, https://github.com/evancchow/jazzml with
express permission.
'''

from __future__ import print_function

from music21 import *
from collections import defaultdict, OrderedDict
#from itertools import groupby, izip_longest
from itertools import groupby, zip_longest
from grammar import *
import sys

#----------------------------HELPER FUNCTIONS----------------------------------#

# 获取melody和chord音轨编号
def __melody_chord(midi_data):
    #自动判断melody chord音轨
    melody_voice = stream.Voice()
    chord_voice = stream.Voice()
    #判断音轨方法
    #melody取非空note所占比例最小
    #chord取chorrd.Chord数量最多
    note_len = []
    melody_len = []
    chord_len = []
    melody_ratio = []
    for data in midi_data:
        note_len.append(len(data.flat.getElementsByClass(
            [note.Rest, note.Note]).elements))
        melody_voice = data.flat.getElementsByClass([note.Note])
        chord_voice = data.flat.getElementsByClass([chord.Chord])
        melody_len.append(len(melody_voice.elements))
        chord_len.append(len(chord_voice.elements))
        melody_ratio.append(melody_len[-1]/note_len[-1])
        # print(melody_voice.elements)
        # print(chord_voice.elements)
        # sys.exit(0)
    # print(note_len)
    # print(melody_len)
    # print(chord_len)
    # print(melody_ratio)
    # print(chord_ratio)
    i_melody = melody_ratio.index(max(melody_ratio))
    i_chord = chord_len.index(max(chord_len))
    print(i_melody,i_chord)
    # sys.exit()
    return i_melody,i_chord

def __offset(midi_data,i_melody,i_chord):
    melody_voice = stream.Voice()
    chord_voice = stream.Voice()
    #读取melody和chord数据
    melody_voice = midi_data[i_melody].flat.getElementsByClass([note.Note,note.Rest])
    chord_voice = midi_data[i_chord].flat.getElementsByClass([chord.Chord])
    #得到melody和chord的offset数据（表示时间）
    melody_offset = [melody.offset//1 for melody in melody_voice]
    chord_offset = [chord.offset//1 for chord in chord_voice]
    #合并offset数据，用于找共同片段
    comp_offset = []
    for temp_offset in melody_offset:
        if (temp_offset in chord_offset) and (temp_offset not in comp_offset):
            comp_offset.append(temp_offset)
    
    # print(melody_offset)
    # print(melody_voice.elements)
    # print(chord_offset)
    # print(chord_voice.elements)
    # print(comp_offset)
    # sys.exit()

    #自动从melody chord音轨识别出连续长度超过min_len部分
    #相邻offset相差超过max_sub视为不连续
    l_offset = []
    r_offset = []
    max_sub = 8
    min_len = 60
    start_offset = comp_offset[0]
    l_offset.append(comp_offset[0])
    end_offset = 0.0
    for i in range(len(comp_offset)-1):
        if (comp_offset[i+1] - comp_offset[i]) > max_sub:
            end_offset = comp_offset[i]
            start_offset = comp_offset[i+1]
            l_offset.append(start_offset)
            r_offset.append(end_offset)
    r_offset.append(comp_offset[-1])

    # 计算每个片段长度
    len_offset = [r - l for r,l in zip(r_offset,l_offset)]

    #删除长度太短的片段
    sum_del = 0
    for i in range(len(len_offset)):
        if(len_offset[i]<min_len):
            del l_offset[i-sum_del]
            del r_offset[i-sum_del]
            sum_del +=1
    l_offset = [temp_offset - temp_offset%4 for temp_offset in l_offset]
    r_offset = [temp_offset - temp_offset%4 for temp_offset in r_offset]

    #保证至少找到了一段符合要求的音乐片段
    assert len(l_offset) > 0
    print(l_offset)
    print(r_offset)

    # 一些后续处理
    for i in melody_voice:
        if i.quarterLength == 0.0:
            i.quarterLength = 0.25

    # Change key signature to adhere to comp_stream (1 sharp, mode = major).
    # Also add Electric Guitar. 
    melody_voice.insert(0, instrument.ElectricGuitar())
    #melody_voice.insert(0, key.KeySignature(sharps=1, mode='major'))
    melody_voice.insert(0, key.KeySignature(sharps=1).getScale('major'))

    return l_offset,r_offset

''' Helper function to parse a MIDI file into its measures and chords '''
def __parse_midi(data_fn,data_para):
    # Parse the MIDI data for separate melody and accompaniment parts.
    midi_data = converter.parse(data_fn)

    i_melody,i_chord = __melody_chord(midi_data)

    #读取音轨数据
    # i_melody = data_para[0]
    # i_chord = data_para[1]
    l_offset,r_offset = __offset(midi_data,i_melody,i_chord)

    # melody_voice
    full_stream = stream.Voice()
    full_stream.append(midi_data[i_chord].flat)
    full_stream.append(midi_data[i_melody].flat)
    
    # print(full_stream[0].elements)
    # print(full_stream[-1].elements)
    # sys.exit(0)

    # Extract solo stream, assuming you know the positions ..ByOffset(i, j).
    # Note that for different instruments (with stream.flat), you NEED to use
    # stream.Part(), not stream.Voice().
    solo_stream = stream.Voice()
    for part in full_stream:
        curr_part = stream.Part()
        curr_part.append(part.getElementsByClass(instrument.Instrument))
        #取出offset中对应的音乐片段
        for i in range(len(l_offset)):
            curr_part.append(part.getElementsByOffset(l_offset[i], r_offset[i], 
                                                     includeEndBoundary=True))
        cp = curr_part.flat
        solo_stream.insert(cp)
    # print(solo_stream[0].elements)
    # print(solo_stream[-1].elements)
    # sys.exit(0)

    # Group by measure so you can classify. 
    # Note that measure 0 is for the time signature, metronome, etc. which have
    # an offset of 0.0.
    melody_stream = solo_stream[-1]
    # melody_stream.removeByClass(chord.Chord)
    measures = OrderedDict()
    offsetTuples = [(int(n.offset / 4), n) for n in melody_stream]
    measureNum = 0 # for now, don't use real m. nums (119, 120)
    for key_x, group in groupby(offsetTuples, lambda x: x[0]):
        measures[measureNum] = [n[1] for n in group]
        measureNum += 1
    # print(measureNum)
    # print(measures)
    # sys.exit(0)

    # Get the stream of chords.
    # offsetTuples_chords: group chords by measure number.
    chordStream = solo_stream[0]
    chordStream.removeByClass(note.Rest)
    chordStream.removeByClass(note.Note)
    offsetTuples_chords = [(int(n.offset / 4), n) for n in chordStream]

    # Generate the chord structure. Use just track 1 (piano) since it is
    # the only instrument that has chords. 
    # Group into 4s, just like before. 
    chords = OrderedDict()
    measureNum = 0
    for key_x, group in groupby(offsetTuples_chords, lambda x: x[0]):
        chords[measureNum] = [n[1] for n in group]
        measureNum += 1
    # print(measureNum)
    # print(chords)
    # sys.exit(0)

    # print(measures)
    # print(chords)
    # sys.exit(0)
    #一些情况下chords和measures长度不等，通过删除使两者长度相同
    while(len(chords) > len(measures)):
        print('warning:the length of chords is greater than the length of measures')
        del chords[len(chords) - 1]
    while(len(chords) < len(measures)):
        print('warning:the length of measures is greater than the length of chords')
        del measures[len(measures) - 1]    
    #两者长度相等且非空
    assert len(chords) == len(measures)
    assert len(chords) != 1

    return measures, chords

''' Helper function to get the grammatical data from given musical data. '''
def __get_abstract_grammars(measures, chords):
    # extract grammars
    abstract_grammars = []
    for ix in range(1, len(measures)):
        m = stream.Voice()
        for i in measures[ix]:
            m.insert(i.offset, i)
        c = stream.Voice()
        for j in chords[ix]:
            c.insert(j.offset, j)
        parsed = parse_melody(m, c)
        # print(parsed)
        # sys.exit(0)
        abstract_grammars.append(parsed)
    # print(abstract_grammars)
    # print(len(abstract_grammars))
    # sys.exit(0)

    return abstract_grammars

#----------------------------PUBLIC FUNCTIONS----------------------------------#

''' Get musical data from a MIDI file '''
def get_musical_data(data_fn_list,data_para_list):
    assert len(data_fn_list) == len(data_para_list)

    abstract_grammars = []
    for data_fn,data_para in zip(data_fn_list,data_para_list):
        measures, chords = __parse_midi(data_fn, data_para)
        abstract_grammar = __get_abstract_grammars(measures, chords)
        for grammar in abstract_grammar:
            abstract_grammars.append(grammar)

    return chords, abstract_grammars

''' Get corpus data from grammatical data '''
def get_corpus_data(abstract_grammars):
    corpus = [x for sublist in abstract_grammars for x in sublist.split(' ')]
    values = set(corpus)
    # print(corpus)
    # print(values)
    # sys.exit(0)
    val_indices = dict((v, i) for i, v in enumerate(values))
    indices_val = dict((i, v) for i, v in enumerate(values))

    return corpus, values, val_indices, indices_val