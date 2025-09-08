import cv2
try:
    import mediapipe as mp
    MP_AVAILABLE = True
except Exception:
    mp = None
    MP_AVAILABLE = False
import numpy as np
import time
from collections import deque
from typing import Tuple
import base64

class HandDetector:
    def __init__(self, min_detection_confidence=0.7, min_tracking_confidence=0.5):
        # Mediapipe hands initialization
        if MP_AVAILABLE:
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence
            )
            self.mp_draw = mp.solutions.drawing_utils
        else:
            self.mp_hands = None
            self.hands = None
            self.mp_draw = None
        # Motion tracking variables from first code block
        self.hand_history = {"Left": deque(maxlen=10), "Right": deque(maxlen=10)}
        self.hand_motion_status = {"Left": "Unknown", "Right": "Unknown"}
        self.flip_cooldown = {"Left": 0, "Right": 0}
        self.cooldown_frames = 15  # Frames to wait before detecting another flip

    def enhance_low_light(self, image: np.ndarray) -> np.ndarray:
        """Enhance an image captured in low light using CLAHE."""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        l_enhanced = clahe.apply(l)
        enhanced_lab = cv2.merge([l_enhanced, a, b])
        return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    def detect_hands(self, image: np.ndarray) -> Tuple[np.ndarray, list, list]:
        """
        Detect hands, annotate the image, return a list of hand info and motion messages.
        Combines knuckle marking, finger counting, palm detection and motion tracking.
        """
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.hands.process(image_rgb)

        hands_info = []
        motion_messages = []
        image_height, image_width, _ = image.shape

        if results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                # Draw landmarks and connections
                # self.mp_draw.draw_landmarks(
                #     image, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                #     self.mp_draw.DrawingSpec(color=(121, 22, 76), thickness=2, circle_radius=4),
                #     self.mp_draw.DrawingSpec(color=(250, 44, 250), thickness=2, circle_radius=2)
                # )

                hand_type = handedness.classification[0].label  # "Left" or "Right"
                extended_fingers, finger_statuses = self.count_fingers(hand_landmarks, hand_type)
                is_palm_showing = self.is_palm_showing(hand_landmarks, hand_type)
                dorsal_side = not is_palm_showing

                # Add knuckle marking from the second code block:
                # Mark fingertips for all hands
                # finger_tips = [4, 8, 12, 16, 20]  # Thumb and fingertips
                # for tip in finger_tips:
                #     x = int(hand_landmarks.landmark[tip].x * image_width)
                #     y = int(hand_landmarks.landmark[tip].y * image_height)
                #     cv2.circle(image, (x, y), 5, (0, 255, 0), cv2.FILLED)
                
                # Mark knuckles only when dorsal side is showing and for extended fingers
                if dorsal_side:
                    finger_data = [
                        {"name": "Thumb",  "tip": 4,  "pip": 3,  "status": finger_statuses[0]},
                        {"name": "Index",  "tip": 8,  "pip": 6,  "status": finger_statuses[1]},
                        {"name": "Middle", "tip": 12, "pip": 10, "status": finger_statuses[2]},
                        {"name": "Ring",   "tip": 16, "pip": 14, "status": finger_statuses[3]},
                        {"name": "Pinky",  "tip": 20, "pip": 18, "status": finger_statuses[4]}
                    ]
                    for finger in finger_data:
                        if finger["status"]:
                            landmark = hand_landmarks.landmark[finger["pip"]]
                            cx, cy = int(landmark.x * image_width), int(landmark.y * image_height)
                            # cv2.circle(image, (cx, cy), 10, (0, 255, 0), cv2.FILLED)Â 

                # Track motion using first code block's routines
                motion_data = self.track_hand_motion(hand_landmarks, hand_type, is_palm_showing)
                if motion_data:
                    motion_messages.append(motion_data)

                # Prepare hand info dictionary
                hands_info.append({
                    'hand_type': hand_type,
                    'finger_count': extended_fingers,
                    'palm_showing': is_palm_showing,
                    'dorsal_side': dorsal_side,
                    'finger_statuses': finger_statuses,
                    'motion_status': self.hand_motion_status[hand_type],
                    'landmarks': hand_landmarks.landmark
                })
        else:
            # No hands detected; reset tracking for both hands
            for hand_type in ["Left", "Right"]:
                if len(self.hand_history[hand_type]) > 0:
                    self.hand_history[hand_type].clear()
                    self.hand_motion_status[hand_type] = "Unknown"

        # Update flip cooldown timers for both hands
        for hand_type in ["Left", "Right"]:
            if self.flip_cooldown[hand_type] > 0:
                self.flip_cooldown[hand_type] -= 1

        return image, hands_info, motion_messages

    def track_hand_motion(self, hand_landmarks, hand_type, is_palm_showing):
        """
        Track hand motion over several frames to detect flips and other significant movements.
        """
        # Extract key landmarks for motion tracking
        wrist = hand_landmarks.landmark[0]
        index_mcp = hand_landmarks.landmark[5]
        pinky_mcp = hand_landmarks.landmark[17]
        middle_tip = hand_landmarks.landmark[12]

        wrist_pos = np.array([wrist.x, wrist.y, wrist.z])
        index_pos = np.array([index_mcp.x, index_mcp.y, index_mcp.z])
        pinky_pos = np.array([pinky_mcp.x, pinky_mcp.y, pinky_mcp.z])
        middle_tip_pos = np.array([middle_tip.x, middle_tip.y, middle_tip.z])

        # Calculate normal vector (hand orientation)
        normal = np.cross(index_pos - wrist_pos, pinky_pos - wrist_pos)
        norm_val = np.linalg.norm(normal)
        if norm_val > 0:
            normal = normal / norm_val
        else:
            normal = normal

        # Current data for this frame
        current_data = {
            "wrist": wrist_pos,
            "normal": normal,
            "is_palm_showing": is_palm_showing,
            "middle_tip": middle_tip_pos
        }

        # Append current frame data to history
        self.hand_history[hand_type].append(current_data)
        if len(self.hand_history[hand_type]) < 5:
            return None

        # Detect flipping motion from history
        return self.detect_flipping_motion(hand_type)

    def detect_flipping_motion(self, hand_type):
        """
        Use the change in palm orientation and normal vector to determine a flipping motion.
        """
        if self.flip_cooldown[hand_type] > 0:
            return None

        history = self.hand_history[hand_type]
        if len(history) < 5:
            return None

        oldest_palm = list(history)[0]["is_palm_showing"]
        newest_palm = list(history)[-1]["is_palm_showing"]

        normals = [data["normal"][2] for data in history]
        normal_changes = [normals[i+1] - normals[i] for i in range(len(normals)-1)]
        avg_change = sum(normal_changes) / len(normal_changes) if normal_changes else 0

        if oldest_palm != newest_palm:
            normal_velocity = abs(avg_change)
            if normal_velocity > 0.015:
                flip_direction = "Palm to Back" if not newest_palm else "Back to Palm"
                self.hand_motion_status[hand_type] = f"Flipping: {flip_direction}"
                self.flip_cooldown[hand_type] = self.cooldown_frames
                return f"{hand_type} Hand flipped: {flip_direction} (velocity: {normal_velocity:.4f})"

        if len(history) >= 3:
            wrist_positions = [list(history)[i]["wrist"] for i in range(-3, 0)]
            wrist_movement = np.linalg.norm(wrist_positions[-1] - wrist_positions[0])
            if wrist_movement > 0.05:
                self.hand_motion_status[hand_type] = "Moving"
            elif abs(avg_change) > 0.01:
                self.hand_motion_status[hand_type] = "Rotating"
            else:
                self.hand_motion_status[hand_type] = "Stable"

        return None

    def count_fingers(self, hand_landmarks, hand_type):
        """
        Count the number of extended fingers based on landmark positions.
        Returns both the count and a list indicating which fingers are extended.
        """
        finger_tips = [8, 12, 16, 20]  # Index, Middle, Ring, Pinky tips
        thumb_tip = 4
        thumb_ip = 3
        points = [(hand_landmarks.landmark[idx].x, hand_landmarks.landmark[idx].y, hand_landmarks.landmark[idx].z) for idx in range(21)]
        finger_statuses = [False] * 5

        palm_showing = self.is_palm_showing(hand_landmarks, hand_type)

        if hand_type == "Left":
            finger_statuses[0] = points[thumb_tip][0] > points[thumb_ip][0] if palm_showing else points[thumb_tip][0] < points[thumb_ip][0]
        else:
            finger_statuses[0] = points[thumb_tip][0] < points[thumb_ip][0] if palm_showing else points[thumb_tip][0] > points[thumb_ip][0]

        for i, tip in enumerate(finger_tips):
            finger_statuses[i + 1] = points[tip][1] < points[tip - 2][1]

        return sum(finger_statuses), finger_statuses

    def is_palm_showing(self, hand_landmarks, hand_type) -> bool:
        """
        Determine if the palm is facing the camera using a normal vector computed from key landmarks.
        """
        wrist = hand_landmarks.landmark[0]
        index_mcp = hand_landmarks.landmark[5]
        pinky_mcp = hand_landmarks.landmark[17]

        wrist_np = np.array([wrist.x, wrist.y, wrist.z])
        index_np = np.array([index_mcp.x, index_mcp.y, index_mcp.z])
        pinky_np = np.array([pinky_mcp.x, pinky_mcp.y, pinky_mcp.z])

        # Compute the normal via cross product
        normal = np.cross(index_np - wrist_np, pinky_np - wrist_np)
        if hand_type == "Right":
            return normal[2] > 0
        else:
            return normal[2] < 0


    def detect_hands_from_landmarks(self, image, multi_hand_landmarks, multi_handedness):
        """
        Android path: consume landmarks & handedness produced by MediaPipe Tasks (Java/Kotlin).
        `multi_hand_landmarks`: list of 21-point lists; each point is dict with x,y,z in normalized coords [0..1].
        `multi_handedness`: list of strings "Left"/"Right" matching landmarks list.
        """
        hands_info = []
        motion_messages = []
        image_height, image_width, _ = image.shape

        for hand_landmarks, handed in zip(multi_hand_landmarks, multi_handedness):
            class _P: pass
            class _H: pass
            hl = _H()
            hl.landmark = []
            for p in hand_landmarks:
                pt = _P()
                pt.x, pt.y, pt.z = p["x"], p["y"], p.get("z", 0.0)
                hl.landmark.append(pt)

            hand_type = handed
            extended_fingers, finger_statuses = self.count_fingers(hl, hand_type)
            is_palm_showing = self.is_palm_showing(hl, hand_type)
            dorsal_side = not is_palm_showing

            if dorsal_side:
                for pip_idx, active in zip([3, 6, 10, 14, 18], finger_statuses):
                    if active:
                        landmark = hl.landmark[pip_idx]
                        cx, cy = int(landmark.x * image_width), int(landmark.y * image_height)
                        # cv2.circle(image, (cx, cy), 10, (0, 255, 0), cv2.FILLED)

            motion_data = self.track_hand_motion(hl, hand_type, is_palm_showing)
            if motion_data:
                motion_messages.append(motion_data)

            hands_info.append({
                "hand_type": hand_type,
                "finger_count": extended_fingers,
                "palm_showing": is_palm_showing,
                "dorsal_side": dorsal_side,
                "finger_statuses": finger_statuses,
                "motion_status": self.hand_motion_status[hand_type],
                "landmarks": hl.landmark,
            })

        return image, hands_info, motion_messages

def main(data, landmarks=None, handedness=None):
    print("main called")
    decoded_data = base64.b64decode(data)
    np_data = np.frombuffer(decoded_data, np.uint8)
    frame = cv2.imdecode(np_data, cv2.IMREAD_UNCHANGED)
    print("image decoded")

    if frame is None:
        raise ValueError("Failed to decode image from input data.")

    print("\n=== Hand Detection, Motion & Knuckle Tracking ===\n")
    
    # Default settings
    detection_confidence = 0.7
    enhance_light = True
    flip_status = True
    
    print(f"Settings:")
    print(f"- Detection Confidence: {detection_confidence}")
    print(f"- Low-light Enhancement: {'Enabled' if enhance_light else 'Disabled'}")
    print(f"- Flipped Camera View: {'Enabled' if flip_status else 'Disabled'}\n")
    
    # Initialize detector
    detector = HandDetector(min_detection_confidence=detection_confidence)
    
    motion_log = []
    previous_hands_info = None
    hands_present = False

    # Optionally flip the frame horizontally
    if flip_status:
        frame = cv2.flip(frame, 1)

    if enhance_light:
        frame = detector.enhance_low_light(frame)

    # Process the frame
    _, hands_info, motion_messages = detector.detect_hands(frame)
    
    # Check if hands status changed
    if (not hands_present and hands_info) or (hands_present and not hands_info):
        if hands_info:
            print("\n--- Hands Detected ---")
            hands_present = True
        else:
            print("\n--- No Hands Detected ---")
            hands_present = False

    # If hands are present, check for significant changes
    if hands_info:
        print_info = False
        if previous_hands_info is None or len(previous_hands_info) != len(hands_info):
            print_info = True
        else:
            for i, hand in enumerate(hands_info):
                if i >= len(previous_hands_info):
                    print_info = True
                    break
                prev_hand = previous_hands_info[i]
                if (hand['hand_type'] != prev_hand['hand_type'] or
                    hand['finger_count'] != prev_hand['finger_count'] or
                    hand['palm_showing'] != prev_hand['palm_showing'] or
                    hand['dorsal_side'] != prev_hand['dorsal_side'] or
                    hand['motion_status'] != prev_hand['motion_status'] or
                    hand['finger_statuses'] != prev_hand['finger_statuses']):
                    print_info = True
                    break

        if print_info:
            timestamp = time.strftime("%H:%M:%S")
            print(f"\n[{timestamp}] Hand Status Update:")
            for idx, hand in enumerate(hands_info):
                print(f"Hand {idx + 1}:")
                print(f"- Type: {hand['hand_type']}")
                print(f"- Fingers Extended: {hand['finger_count']}")
                print(f"- Palm Showing: {'Yes' if hand['palm_showing'] else 'No'}")
                print(f"- Dorsal Side: {'Yes' if hand['dorsal_side'] else 'No'}")
                print(f"- Motion: {hand['motion_status']}")
                
                if hand['dorsal_side']:
                    finger_names = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
                    marked_knuckles = [finger_names[i] for i, status in enumerate(hand['finger_statuses']) if status]
                    if marked_knuckles:
                        print(f"- Marked Knuckles: {', '.join(marked_knuckles)}")
                    else:
                        print("- No knuckles marked (no extended fingers)")
                else:
                    print("- No knuckles marked (palm side showing)")
                print()

    # Always log motion messages
    if motion_messages:
        timestamp = time.strftime("%H:%M:%S")
        for msg in motion_messages:
            motion_log.append(f"[{timestamp}] {msg}")
            print(f"Motion detected: [{timestamp}] {msg}")
            if "flip" in msg.lower():
                print(f"***FLIPPING MOTION DETECTED*** [{timestamp}] {msg}")
        if len(motion_log) > 20:
            motion_log = motion_log[-20:]
    
    previous_hands_info = hands_info.copy() if hands_info else None
    
    print("\nProcessing finished")

    return {
        "hands_info": hands_info,
        "motion_log": motion_log,
        "processed_frame": frame
    }