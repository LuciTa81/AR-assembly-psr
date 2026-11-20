"""Check a known-changing Unity capture; a static scene may legitimately fail."""
import argparse
import subprocess

from record_take import FFMPEG


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('video')
    parser.add_argument('--seconds', type=int, default=10)
    args = parser.parse_args()
    result = subprocess.run(
        [str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-i', args.video,
         '-t', str(args.seconds), '-vf', 'fps=1,scale=960:270,format=gray',
         '-f', 'rawvideo', 'pipe:1'], capture_output=True, check=True)
    size = 960 * 270
    frames = [result.stdout[i:i + size] for i in range(0, len(result.stdout), size)]
    changes = [sum(abs(a - b) > 20 for a, b in zip(previous, current))
               for previous, current in zip(frames, frames[1:])]
    print({'sampled_frames': len(frames), 'changed_pixels': changes})
    assert len(frames) >= 2 and all(len(frame) == size for frame in frames)
    assert max(changes, default=0) >= 100, 'No substantive screen change captured'


if __name__ == '__main__':
    main()
