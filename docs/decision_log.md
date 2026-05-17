# State Definition

## Main States

| ID | Name | Description |
|---|---|---|
| S0 | Idle_Open_Empty | The enclosure is open and empty. |
| S1 | PCB_Placed | The dummy PCB is placed in the correct pose. |
| S2 | Lid_Closed_Aligned | The lid is closed and alignment is correct. |
| S3 | Screw_A_Done | Screw A is confirmed as completed. |
| S4 | Screw_B_Done | Screw B is confirmed as completed. |
| S5 | Screw_C_Done | Screw C is confirmed as completed. |
| S6 | Screw_D_Done | Screw D is confirmed as completed. |
| S7 | Finish | All required steps are complete. |

## Error Flags

| ID | Name | Description |
|---|---|---|
| E1 | PCB_Missing | PCB evidence is missing when a later step is attempted. |
| E2 | Lid_Misaligned | Lid is closed but alignment is not valid. |
| E3 | Wrong_Order | A later step is attempted before required prior steps. |
| E4 | Step_Not_Confirmed | Evidence is insufficient to confirm completion. |

## ROI Classes

### PCB ROI
- empty
- wrong_pose
- correct_pose
- occluded

### Lid ROI
- open
- misaligned
- aligned

### Screw ROI
- empty
- progress
- done

## Labeling Rule Notes
- `progress` includes ongoing tightening, tool contact, partial visibility, and visually ambiguous in-progress states.
- `done` should only be assigned when the visual evidence is strong enough to confirm completion.
- ambiguous screw cases should prefer `progress` over `done`.
