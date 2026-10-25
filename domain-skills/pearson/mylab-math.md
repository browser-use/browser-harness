# Pearson MyLab Math player

The course shell is on mylabmastering.pearson.com. Homework launches a separate player page on mylab.pearson.com/Student/PlayerHomework.aspx with homeworkId and cId parameters. The actual question UI may be nested in cross-origin assignmentplayer and Player.aspx frames. Coordinate interactions pass through these frames.

The math editor interprets typed ^ and / structurally. Enter multi-term expressions in chunks: finish an exponent and use ArrowRight to return to the baseline before entering the next term. A fractional exponent can require two ArrowRight presses, one to leave the denominator and one to leave the exponent. Avoid unnecessary parentheses around simple exponents. Inspect the rendered expression before checking an answer.

Use text insertion for printable characters; raw printable key dispatch can duplicate text. Allow focus and rendering to settle before insertion. The first click on Check answer can only blur the math editor; inspect state and click again if it has not submitted.

Correct-answer dialogs advance either to the next part or next question. Some multipart questions also require Continue after dismissing the dialog. Read each newly displayed part before acting.

Save can close the player tab. Re-select the course shell afterward. A previously open homework overview can show a stale summary score while its question list has updated. Reload the shell and use the assignment list's see score link to verify the recorded grade.

Screenshots can have different devicePixelRatio across the popup and course shell. Convert image pixels to CSS coordinates using the current viewport and screenshot size; do not reuse a popup's scale in the shell.

## Economics graphs and answer fields

Three-point curves use endpoint, middle, endpoint order. Finish multipoint curves by selecting the arrow tool. Select an object before opening its label menu and verify the chosen label appears. Plot equilibrium points before overlapping curves. Use Edit coordinates when exact numeric values are required.

Selecting a drawing tool can change the instruction bar height and move the graph. Selecting a point can also expose an editing bar that moves the graph again. Take a fresh screenshot after each transition before mapping graph coordinates. Clicking a node can move or snap it, so verify its coordinates afterward.

The label menu requires an actively selected object. After finishing a curve with the arrow tool, select the curve body before opening its label menu. For a point overlapping a line, click blank graph space to deselect, then select the point. In the coordinate editor, editing X can resize the field and shift Y; enter Y first or re-locate Y after editing X.

Text fields can resize and reflow the entire line after insertion. Wait for rendering and locate the next field from a fresh screenshot. To replace a field, focus it, wait, press Home then Shift+End, and insert the replacement. Tab can duplicate characters in the math editor; inspect the final expression before submitting.

An immediate click-and-type batch can miss focus in these embedded fields. Capture after focusing, allow the field to settle, insert text, then capture again to confirm it landed in the intended field. A delay alone has not always been sufficient.

Dropdown options may only become highlighted on the first click. Verify the committed text. Enter can commit an open menu, but when the menu is already closed it may activate Check answer.

For nested homework panes, clicking the content and pressing PageDown can scroll when a mouse wheel command stalls. Reapply viewport emulation after switching tabs before reusing screenshot coordinates.

Question navigation can take substantially longer than part transitions. Wait for the question header to change before clicking another navigation control; repeated clicks can skip a question. After committing a dropdown, inspect all fields before pressing Enter again, since Enter can submit the final part.

Some economics questions display a green correct-answer heading while the explanatory body erroneously says an answer is incorrect. Verify that the player advances and records full credit before treating the body text as a failed submission.

In reserve/deposit tables with instructions to reuse rounded values, calculate reserves first, round them, then subtract those rounded reserves from deposits to obtain loans. Independently rounding deposits times the lending fraction can differ by one dollar and be rejected.

The Final check label can carry over to a newly displayed part even when that part has not yet been attempted. Read the current part and verify its fields; the button label alone does not establish its attempt history. A correction accepted at Final check can retain full credit, while a rejected Final check can lock that part. Verify the eventual question score.
