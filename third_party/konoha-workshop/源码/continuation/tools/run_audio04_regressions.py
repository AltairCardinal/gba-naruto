from pathlib import Path
import os,subprocess,json
R=Path(__file__).resolve().parents[2];node='/home/app/venvs/pig/lib/python3.12/site-packages/playwright/driver/node';out=R/'continuation/evidence';restart=R/'continuation/build/naruto_restart_v043_AUDIO04.gba';cont=R/'continuation/build/naruto_continuation_v043_AUDIO04.gba'
steps=[
('static',[node,'continuation/tools/validate_release_regressions.js',str(restart),str(cont)],{}),
('default',['python3','continuation/tools/check_narration.py'],{'NARUTO_REPLAY_ROM':str(restart),'NARUTO_REPLAY_NAME':'audio04_opening_default'}),
('substitute',['python3','continuation/tools/check_narration.py'],{'NARUTO_REPLAY_ROM':str(restart),'NARUTO_REPLAY_NAME':'audio04_opening_substitute','NARUTO_OPENING_SUBSTITUTE':'1'}),
('restart_paths',['python3','continuation/tools/check_restart_paths.py'],{'NARUTO_REPLAY_ROM':str(restart),'NARUTO_REPLAY_NAME':'audio04_first_three_paths'}),
('save_restart',['python3','continuation/tools/save_resume.py'],{'NARUTO_SAVE_ROM':str(restart),'NARUTO_SAVE_NAME':'audio04_save_restart'}),
('save_continuation',['python3','continuation/tools/save_resume.py'],{'NARUTO_SAVE_ROM':str(cont),'NARUTO_SAVE_INPUT':str(R/'originals/user_clear_no_stat_points.sav'),'NARUTO_SAVE_SCENE':'57','NARUTO_SAVE_NAME':'audio04_save_continuation'}),
('narration_ui',[node,'continuation/tools/check_narration_ui.js'],{'NARUTO_NARRATION_TAG':'v043_AUDIO04','NARUTO_UI_VERSION':'0.4.3','NARUTO_UI_OUT':'audio04_narration_ui'}),
('narration_export',['python3','continuation/tools/check_narration_export.py'],{'NARUTO_EXPORT_ROM':str(out/'audio04_narration_ui/narration_export.gba'),'NARUTO_EXPORT_TEST_NAME':'audio04_narration_export'})]
for label,cmd,env in steps:
 print('START',label,flush=True)
 p=subprocess.run(cmd,cwd=R,env={**os.environ,**env},stdout=(out/f'audio04_{label}.log').open('w'),stderr=subprocess.STDOUT)
 print('END',label,p.returncode,flush=True)
 if p.returncode:raise SystemExit(p.returncode)
