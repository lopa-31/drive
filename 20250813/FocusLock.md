Of course! Implementing a focus lock like in pro camera apps involves a specific sequence of states and requests using the Camera2 API. It's more than a simple tap-to-focus; it's about telling the camera to focus once at a specific point and then *hold* that focus distance until you explicitly unlock it.

Here is a complete guide and a practical code example in Kotlin to achieve this.

### The Core Concept of Focus Lock in Camera2

The process can be broken down into a state machine:

1.  **State 1: UNLOCKED (Continuous Auto-Focus)**
    *   This is the default state. The camera continuously adjusts focus automatically.
    *   **Camera2 Settings:**
        *   `CONTROL_AF_MODE` is `CONTROL_AF_MODE_CONTINUOUS_PICTURE` or `CONTROL_AF_MODE_CONTINUOUS_VIDEO`.
        *   This is set on the repeating request for the preview.

2.  **State 2: TRIGGERING (Focusing on a Point)**
    *   The user taps the screen. You calculate the tap area and tell the camera to start focusing on that specific region.
    *   **Camera2 Settings:**
        *   Switch `CONTROL_AF_MODE` to `CONTROL_AF_MODE_AUTO`.
        *   Set `CONTROL_AF_REGIONS` to a `MeteringRectangle` representing the tap area.
        *   Set `CONTROL_AF_TRIGGER` to `CONTROL_AF_TRIGGER_START` to initiate the focus scan.
        *   This request is sent as a single capture, while you wait for the result in the `CaptureCallback`.

3.  **State 3: LOCKED (Focus is Held)**
    *   The camera's hardware reports back that it has successfully focused.
    *   The key is to *not* return to continuous auto-focus. The focus is now locked at the distance achieved in State 2.
    *   **Camera2 Settings:**
        *   After receiving the `CONTROL_AF_STATE_FOCUSED_LOCKED` state in your `CaptureCallback`, you must tell the camera to stop the trigger.
        *   You update your repeating preview request by setting `CONTROL_AF_TRIGGER` to `CONTROL_AF_TRIGGER_IDLE`. This "commits" the lock. The `CONTROL_AF_MODE` remains `AUTO`.

4.  **Unlocking:**
    *   The user taps an "unlock" button or taps the screen again.
    *   You cancel the current focus lock and return to the default continuous auto-focus state.
    *   **Camera2 Settings:**
        *   Set `CONTROL_AF_TRIGGER` to `CONTROL_AF_TRIGGER_CANCEL` to cancel the lock.
        *   Set `CONTROL_AF_MODE` back to `CONTROL_AF_MODE_CONTINUOUS_PICTURE`.
        *   Apply these settings to your repeating preview request.

---

### Step-by-Step Implementation (Kotlin)

Let's put this into a working example. Assume you already have a `TextureView`, a `CameraDevice`, and a `CameraCaptureSession` set up.

#### 1. Manage Focus State

It's helpful to use an enum to manage the current state.

```kotlin
private enum class FocusState {
    UNLOCKED, // Continuous AF
    TRIGGERING, // Focus sequence has been triggered
    LOCKED      // Focus is locked
}

private var focusState = FocusState.UNLOCKED
```

#### 2. Set Up the Initial Preview (Unlocked State)

When you create your repeating request for the preview, set it to continuous auto-focus.

```kotlin
// In your createCameraPreviewSession() method
previewRequestBuilder.apply {
    // This is our default state: continuous auto-focus
    set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
    set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON_AUTO_FLASH)
}

// Set the repeating request
captureSession.setRepeatingRequest(previewRequestBuilder.build(), captureCallback, backgroundHandler)
```

#### 3. Handle Touch Events to Trigger Focus

Add an `OnTouchListener` to your `TextureView`.

```kotlin
textureView.setOnTouchListener { view, event ->
    if (event.action == MotionEvent.ACTION_DOWN) {
        // If we are already locked, a tap should unlock and refocus.
        // If we are unlocked, a tap should trigger a lock.
        if (focusState == FocusState.LOCKED) {
            unlockFocus()
        } else {
            lockFocus(event.x, event.y)
        }
        return@setOnTouchListener true
    }
    false
}
```

#### 4. The `lockFocus()` Method

This is where the magic starts. It converts view coordinates to sensor coordinates and triggers the focus sequence.

```kotlin
private fun lockFocus(x: Float, y: Float) {
    if (focusState == FocusState.TRIGGERING) return // Don't tap-spam

    try {
        // 1. Get the sensor characteristics
        val characteristics = cameraManager.getCameraCharacteristics(cameraId)
        val sensorRect = characteristics.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)
            ?: return

        // 2. Convert tap coordinates to sensor coordinates
        // The sensor may be oriented differently from the screen.
        val sensorOrientation = characteristics.get(CameraCharacteristics.SENSOR_ORIENTATION)!!
        val currentDisplayRotation = display!!.rotation

        // Invert x and y for the coordinate transformation
        val newY = (x / textureView.width) * sensorRect.height()
        val newX = (y / textureView.height) * sensorRect.width()

        val halfTouchWidth = 150 // A good default value
        val halfTouchHeight = 150
        val meteringRect = MeteringRectangle(
            max(newX.toInt() - halfTouchWidth, 0),
            max(newY.toInt() - halfTouchHeight, 0),
            halfTouchWidth * 2,
            halfTouchHeight * 2,
            MeteringRectangle.METERING_WEIGHT_MAX - 1
        )

        // 3. Update the state and build the request
        focusState = FocusState.TRIGGERING

        previewRequestBuilder.apply {
            // We need to switch to AUTO mode for the trigger to work
            set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_AUTO)
            // Set the focus area
            set(CaptureRequest.CONTROL_AF_REGIONS, arrayOf(meteringRect))
            // Also set the auto-exposure area
            set(CaptureRequest.CONTROL_AE_REGIONS, arrayOf(meteringRect))
            // Start the trigger
            set(CaptureRequest.CONTROL_AF_TRIGGER, CameraMetadata.CONTROL_AF_TRIGGER_START)
        }

        // 4. Send the request for a single capture to trigger the focus
        captureSession.capture(previewRequestBuilder.build(), captureCallback, backgroundHandler)

    } catch (e: CameraAccessException) {
        Log.e(TAG, "lockFocus failed", e)
    }
}
```

#### 5. Monitor the Result in `CaptureCallback`

The `CameraCaptureSession.CaptureCallback` is where you listen for the camera hardware to report its state.

```kotlin
private val captureCallback = object : CameraCaptureSession.CaptureCallback() {

    private fun process(result: CaptureResult) {
        when (focusState) {
            FocusState.TRIGGERING -> {
                val afState = result.get(CaptureResult.CONTROL_AF_STATE)
                if (afState == null) {
                    // If AF state is not available, we can't lock focus. End the sequence.
                    Log.d(TAG, "AF state is null, cannot lock focus.")
                    unlockFocus()
                    return
                }

                if (afState == CaptureResult.CONTROL_AF_STATE_FOCUSED_LOCKED ||
                    afState == CaptureResult.CONTROL_AF_STATE_NOT_FOCUSED_LOCKED
                ) {
                    // AF sequence is complete.
                    Log.d(TAG, "Focus lock sequence complete. AF State: $afState")

                    // 7. Tell the camera to stop triggering AF. This "commits" the lock.
                    previewRequestBuilder.set(CaptureRequest.CONTROL_AF_TRIGGER, CameraMetadata.CONTROL_AF_TRIGGER_IDLE)
                    captureSession.setRepeatingRequest(previewRequestBuilder.build(), this, backgroundHandler)

                    // 8. Update our internal state to LOCKED
                    focusState = FocusState.LOCKED
                    
                    // TODO: Update UI to show a "locked" icon
                }
            }
            FocusState.LOCKED -> {
                // Do nothing, focus is already locked.
            }
            FocusState.UNLOCKED -> {
                // The camera is in continuous AF mode.
            }
        }
    }

    override fun onCaptureProgressed(session: CameraCaptureSession, request: CaptureRequest, partialResult: CaptureResult) {
        process(partialResult)
    }

    override fun onCaptureCompleted(session: CameraCaptureSession, request: CaptureRequest, result: TotalCaptureResult) {
        process(result)
    }
}
```

#### 6. The `unlockFocus()` Method

This method returns the camera to its default continuous auto-focus state.

```kotlin
fun unlockFocus() {
    if (focusState == FocusState.UNLOCKED) return

    try {
        focusState = FocusState.UNLOCKED

        previewRequestBuilder.apply {
            // 1. Return to continuous AF
            set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
            // 2. Cancel any ongoing AF trigger
            set(CaptureRequest.CONTROL_AF_TRIGGER, CameraMetadata.CONTROL_AF_TRIGGER_CANCEL)
        }

        // 3. Set the repeating request to restart the preview with the new settings
        captureSession.setRepeatingRequest(previewRequestBuilder.build(), captureCallback, backgroundHandler)

        // TODO: Update UI to remove the "locked" icon

    } catch (e: CameraAccessException) {
        Log.e(TAG, "unlockFocus failed", e)
    }
}
```

### Important Considerations

*   **UI Feedback:** It's crucial to give the user visual feedback.
    *   Draw a rectangle on the screen where the user tapped.
    *   Change the color of the rectangle: Yellow for `TRIGGERING`, Green for `LOCKED`, and Red if the state becomes `CONTROL_AF_STATE_NOT_FOCUSED_LOCKED`.
    *   Show a padlock icon when the focus is in the `LOCKED` state.
*   **Coordinate Transformation:** The conversion from view coordinates to sensor coordinates is tricky. The code above provides a basic implementation. For a fully robust solution, you need to account for the display rotation and the sensor orientation correctly. You can find more detailed helper functions for this online.
*   **Error Handling:** A camera might not support auto-focus or specific modes. Always check `CameraCharacteristics` for available AF modes before trying to set them.
*   **Lifecycle:** Ensure you properly `close()` your `CameraCaptureSession` and `CameraDevice` in `onPause()` and re-open them in `onResume()` to avoid resource leaks. The `focusState` should be reset to `UNLOCKED` when the camera is reopened.