"""Renders a Level Sequence from the RLCity project to JPG frames with Unreal's built-in sequence capture.

    python render.py <LevelSequence path> <map path> preview|full

    python render.py /Game/Construction/Film/LS_Crane.LS_Crane /Game/Construction/Lvl_Construction preview

preview: 640x360, for checking every camera before the full render (about a third of the time).
full:    1920x1080, the frames overlay_*.py turns into clips.

Known-good flags only (2026-11-02). Lessons built in, so they never cost a render again:
- The output folder must have no spaces; with spaces Unreal runs and writes nothing. Frames go to FRAMES below.
- -NoTextureStreaming keeps sign text sharp; -MovieCinematicMode hides the HUD; warm-up frames let lighting settle.
- Before rendering: motion blur off (FilmPPV in the level), camera aperture 22 and focus 100000 (no blur), PlayerStart
  out of shot, and any input Blueprint that moves the same actors disconnected (CraneControl refs set to None).
Unreal's newer Movie Render Queue needs a saved preset made once in the editor (see README, pipeline audit).
"""
import pathlib, subprocess, sys

UE = r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
PROJECT = r"..\FactoryRL.uproject"
FRAMES = pathlib.Path(r"C:\rlfilm")


def main():
    if len(sys.argv) != 4 or sys.argv[3] not in ('preview', 'full'):
        sys.exit(__doc__)
    # Git Bash turns /Game/... into C:/Program Files/Git/Game/... (the editor then crashes on start); undo that here.
    seq, level, mode = [a.replace('\\', '/').split('Program Files/Git', 1)[-1] if 'Program Files/Git' in a.replace('\\', '/') else a
                        for a in sys.argv[1:]]
    out = FRAMES / (pathlib.PurePosixPath(seq).stem.split('.')[0] + '_' + mode)
    assert ' ' not in str(out), 'output folder must have no spaces'
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('*.jpg'):
        f.unlink()
    w, h, q = (640, 360, 85) if mode == 'preview' else (1920, 1080, 95)
    subprocess.run([UE, PROJECT, level, '-game',
                    '-MovieSceneCaptureType=/Script/MovieSceneCapture.AutomatedLevelSequenceCapture',
                    # -RenderOffscreen: no window on the owner's screen (owner, 2026-11-02); still rendered on the GPU.
                    f'-LevelSequence={seq}', '-RenderOffscreen', '-Unattended', '-NoLoadingScreen', f'-ResX={w}', f'-ResY={h}', '-ForceRes',
                    f'-MovieFolder={out}', '-MovieName=f{frame}', '-MovieFormat=JPG', '-MovieFrameRate=30', f'-MovieQuality={q}',
                    '-MovieWarmUpFrames=60', '-MovieCinematicMode=Yes', '-NoScreenMessages', '-NoTextureStreaming', '-NoSound',
                    f'-log=Render_{mode}.log'], check=False)
    n = len(list(out.glob('*.jpg')))
    print(f'{n} frames in {out}')
    if n == 0:
        sys.exit('No frames written: check Saved/Logs/Render_%s.log' % mode)


if __name__ == '__main__':
    main()
