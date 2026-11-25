"""Golden geometry/selection outputs from frozen Python, with synthetic YOLO boxes."""
import json
from types import SimpleNamespace
import numpy as np
import pose_replay_compare as replay
from server.realtime.yolo_realtime import MetricToolPlane, RealtimeYoloAnalyzer


def main():
    camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
    workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
    plane=MetricToolPlane(camera,workspace)
    analyzer=RealtimeYoloAnalyzer(False,'','',metric_plane=plane,nested_driver_dedup=True,handle_linked_driver=True)
    analyzer.centers=plane.centers
    samples=json.loads((replay.ASSETS/'pose-fixtures.json').read_bytes());cases=[]
    for index,sample in enumerate(samples):
        pose,_=replay.baseline({int(k):np.array(v) for k,v in sample['detections'].items()},workspace,camera)
        matrix=plane.homography(dict(received_at=0,analysis=dict(status='tracking',rvec=pose.rvec.reshape(3),tvec_mm=pose.tvec.reshape(3))),0)
        for target in 'ABCD':
            x,y=sample['targets'][target]['pixel']
            shaft=[0,.9,x-4,y-60,x+4,y]
            handle=[1,.85,x-14,y-75,x+14,y-45]
            scenarios=dict(handle=[shaft,handle],no_handle=[shaft],
                overlapping=[shaft,[0,.7,x-4,y-58,x+4,y],handle],
                fragment=[shaft,[0,.6,x-4,y-22,x+4,y],handle],
                unlinked=[shaft,handle,[0,.8,x+56,y-60,x+64,y]],
                ambiguous=[shaft,[0,.8,x+56,y-60,x+64,y]])
            for name,boxes in scenarios.items():
                boxes=np.array(boxes,dtype=np.float32).tolist()
                predictions=[SimpleNamespace(cls=np.array([d[0]]),conf=np.array([d[1]]),xyxy=np.array([d[2:]])) for d in boxes]
                pred=SimpleNamespace(boxes=predictions,names={0:'driver',1:'handle',2:'screw'})
                analyzer.model=SimpleNamespace(predict=lambda **kwargs:[pred])
                features=analyzer._process(1,None,matrix).features
                cases.append(dict(pose_index=index,target=target,scenario=name,boxes=boxes,
                    driver_count=features['driver_count'],tip_source=features.get('tool_tip_source',0),
                    distances=[features[f'tool_dist_{k}'] for k in 'abcd'],
                    scores=[features[f'tool_score_{k}'] for k in 'abcd']))
    path=replay.ROOT/'app/src/androidTest/assets/tool-evidence-fixtures.json'
    with path.open('x',encoding='utf-8') as stream:json.dump(cases,stream,indent=2,allow_nan=False)
    print(f'{len(cases)} frozen-Python cases generated')


if __name__=='__main__':main()
