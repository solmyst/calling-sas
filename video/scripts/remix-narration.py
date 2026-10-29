"""Replace narration while preserving every previously reviewed video frame."""
import hashlib
import json
import subprocess
import wave
from pathlib import Path

VIDEO = Path(__file__).resolve().parents[1]
OUT = VIDEO / 'out'
AUDIO = VIDEO / 'public/audio'
SOURCE = OUT / 'giani-hackathon-demo-v2.mp4'
TARGET = OUT / 'giani-hackathon-demo-v3.mp4'
SLOTS = [('intro', 0, 7), ('configure', 7, 9), ('liveintro', 16, 4),
         ('review', 44, 7), ('outro', 51, 9)]


def run(args):
    return subprocess.check_output(args, stderr=subprocess.PIPE)


def frame_hashes(path):
    # Decode all frames: the new film must inherit the exact validated visuals.
    return run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:v:0',
                '-f', 'framemd5', '-']).decode()


def main():
    review_path = OUT / 'previous/review-v2.json'
    review_path.parent.mkdir(exist_ok=True)
    if not review_path.exists():
        review_path.write_bytes((OUT / 'review-report.json').read_bytes())
    prior = json.loads(review_path.read_text())
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if not prior['passed'] or prior['sha256'] != source_hash:
        raise RuntimeError('Source must match the successful visual review.')
    cast = json.loads((AUDIO / 'voices.json').read_text())
    args = ['ffmpeg', '-v', 'error', '-y', '-i', str(SOURCE)]
    filters, labels = [], []
    for i, (name, start, window) in enumerate(SLOTS, 1):
        path = AUDIO / (name + '.wav')
        with wave.open(str(path)) as audio:
            duration = audio.getnframes() / audio.getframerate()
        if duration > window - .1:
            raise RuntimeError(f'{name} exceeds its narration window.')
        args += ['-i', str(path)]
        filters.append(f'[{i}:a]aresample=48000,volume=0.95,adelay={start*1000}:all=1[n{i}]')
        labels.append(f'[n{i}]')
    args += ['-i', str(AUDIO / 'conversation-edit.wav'), '-i', str(AUDIO / 'bed.wav')]
    filters += [
        '[6:a]aresample=48000,atrim=duration=24,volume=0.95,adelay=20000:all=1[live]',
        "[7:a]aresample=48000,atrim=duration=60,volume='if(between(t,20,43.999),0.035,0.06)':eval=frame[bed]",
        ''.join(labels) + '[live][bed]amix=inputs=7:normalize=0:duration=longest,'
        'loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000,apad,atrim=duration=60[mix]',
    ]
    args += ['-filter_complex', ';'.join(filters), '-map', '0:v:0', '-map', '[mix]',
             '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ac', '2',
             '-t', '60', '-movflags', '+faststart', str(TARGET)]
    run(args)
    source_frames, output_frames = frame_hashes(SOURCE), frame_hashes(TARGET)
    identical = source_frames == output_frames
    count = len([line for line in output_frames.splitlines() if not line.startswith('#')])
    probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                            '-of', 'json', str(TARGET)]))
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    levels = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(TARGET), '-vn', '-af',
                             'loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json', '-f', 'null', '-'],
                            capture_output=True, text=True, check=True).stderr
    audio_stats = json.loads(levels[levels.rfind('{'):levels.rfind('}')+1])
    passed = (identical and count == 3600 and video['r_frame_rate'] == '60/1'
              and abs(float(probe['format']['duration']) - 60) < .02
              and -17 < float(audio_stats['input_i']) < -15
              and float(audio_stats['input_tp']) < 0)
    report = dict(passed=passed, source_sha256=source_hash,
                  sha256=hashlib.sha256(TARGET.read_bytes()).hexdigest(),
                  frames_decoded=count, all_frames_identical=identical,
                  source_visual_review=str(review_path.relative_to(VIDEO)),
                  duration_seconds=float(probe['format']['duration']), fps=60,
                  narration_cast={name:cast[name] for name, _, _ in SLOTS},
                  live_conversation='Existing recording preserved; AI agent: Shivani',
                  audio=audio_stats)
    (OUT / 'voice-remix-review.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k:report[k] for k in ['passed', 'frames_decoded', 'all_frames_identical']}))
    if not passed:
        raise RuntimeError('Audio remix did not pass delivery checks.')


if __name__ == '__main__':
    main()
