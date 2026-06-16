import mediapipe as mp 
import cv2 

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    min_detection_confidence = 0.5,
    min_tracking_confidence = 0.5,
    max_num_hands= 4
)

cap = cv2.VideoCapture(0)

while True:
    success, frame = cap.read()
    if not success:
        break
    
    frame = cv2.flip(frame,1)
    rgb_frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    

    if results.multi_hand_landmarks:
        for hand_landmark in results.multi_hand_landmarks:
            landmark_style= mp_draw.DrawingSpec(color=(0, 255, 0), thickness=3, circle_radius=4)
            connection_style = mp_draw.DrawingSpec(color=(0, 255, 0), thickness=3, circle_radius=4)
            mp_draw.draw_landmarks(
                frame,
                hand_landmark,
                mp_hands.HAND_CONNECTIONS,
                landmark_style,
                connection_style
            )
            tip = hand_landmark.landmark[8]

    cv2.putText (frame,"hello",(10,60),cv2.FONT_HERSHEY_SIMPLEX,1,(255,0,0),0)

    cv2.imshow("HAnd Tracking",frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()