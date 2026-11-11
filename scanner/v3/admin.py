"""Offline local operator CLI: staging only; never touches the live scanning process."""
import argparse,json
from pathlib import Path
from .control import ControlPlane,Event

def main():
    p=argparse.ArgumentParser(description="Ministaut V3 event administration (staging)")
    p.add_argument("--state",default=str(Path(__file__).resolve().parents[1]/"v3_operator_state.json"))
    sub=p.add_subparsers(dest="command",required=True)
    a=sub.add_parser("add");a.add_argument("id");a.add_argument("url");a.add_argument("venue");a.add_argument("kickoff");a.add_argument("title")
    sub.add_parser("list")
    for name in ("pause","activate","needs-map"):sub.add_parser(name).add_argument("id")
    args=p.parse_args();cp=ControlPlane(args.state)
    if args.command=="add":cp.add(Event(args.id,args.url,args.venue,args.kickoff,args.title))
    elif args.command=="list":
        print(json.dumps([{"id":e.id,"title":e.title,"arena":e.venue_id,"status":e.state,"kickoff":e.kickoff_at,"last_success":e.last_success_at} for e in cp.events.values()],ensure_ascii=False,indent=2))
    else:cp.set_state(args.id,{"pause":"paused","activate":"monitoring","needs-map":"needs_map"}[args.command])
if __name__=="__main__":main()
