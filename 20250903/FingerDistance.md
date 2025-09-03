Of course. It's great that you have the first function working for your needs.

Based on your request, here is a clean, self-contained function to calculate the real-time distance of the finger. This function is designed to be robust and clear, assuming, as you specified, that the input `fingerRect` is from the **un-rotated, raw image from the sensor**.

---

### Part 1: The New `calculateFingerDistance` Function

This function takes the detected finger's bounding box and the known physical camera parameters and returns its distance. It is streamlined for this specific purpose.

```kotlin
import android.graphics.Rect
import android.util.Size
import android.util.SizeF

/**
 * Calculates the real-world distance to a finger based on its detected bounding box in an image.
 *
 * IMPORTANT: This function assumes the `fingerRect` coordinates are relative to the raw, un-rotated
 * image from the camera sensor (which is typically in a landscape orientation).
 *
 * @param fingerRect The bounding box of the detected finger in the image's pixel coordinates.
 * @param imageSize The dimensions (width, height) of the image on which the detection was performed.
 * @param sensorPhysicalSize The physical dimensions (width, height) of the camera sensor in millimeters.
 * @param focalLengthMM The focal length of the camera lens in millimeters.
 * @param averageFingerWidthMM The assumed real-world width of the finger in millimeters. This is a crucial calibration parameter.
 * @return The calculated distance to the finger in millimeters, or -1.0f if the width is zero.
 */
fun calculateFingerDistance(
    fingerRect: Rect,
    imageSize: Size,
    sensorPhysicalSize: SizeF,
    focalLengthMM: Float,
    averageFingerWidthMM: Float
): Float {
    val perceivedWidthPixels = fingerRect.width().toFloat()

    // Guard clause: Cannot calculate distance for an object with no width.
    if (perceivedWidthPixels <= 0) {
        return -1.0f
    }

    val imageWidthPixels = imageSize.width.toFloat()

    // Since the fingerRect is from the un-rotated (landscape) image, the relevant
    // physical sensor dimension that corresponds to the image's width is the sensor's physical width.
    val sensorWidthMM = sensorPhysicalSize.width

    // The core similar triangles formula:
    // Distance = (FocalLength * RealObjectWidth * ImageWidth) / (PerceivedObjectWidth * SensorWidth)
    // All units must be consistent (e.g., mm and pixels).
    val distanceMM = (focalLengthMM * averageFingerWidthMM * imageWidthPixels) /
                     (perceivedWidthPixels * sensorWidthMM)

    return distanceMM
}
```

#### How to Use It:

You would call this function from your real-time processing loop (e.g., your `ImageReader.OnImageAvailableListener` or wherever you get the detection result from your Python script).

```kotlin
// Example usage inside your image processing logic:

// 1. Get the detection result (assuming it's a Rect)
val detectedFingerRect: Rect = getFingerRectFromDetector() // e.g., Rect(1800, 800, 2050, 1500)

// 2. You already have these parameters from your camera setup
val currentImageSize = Size(4000, 2250) // The size of the image sent for detection
// sensorPhysicalSize, focalLengthMM, etc.

// 3. Call the new function
val distanceInMillimeters = calculateFingerDistance(
    fingerRect = detectedFingerRect,
    imageSize = currentImageSize,
    sensorPhysicalSize = yourSensorPhysicalSize,
    focalLengthMM = yourFocalLengthMM,
    averageFingerWidthMM = 16.0f // Your assumed finger width
)

if (distanceInMillimeters > 0) {
    Log.d("FingerDistance", "Finger is %.2f cm away".format(distanceInMillimeters / 10.0f))
    // Now you can compare this distance with your min/max safe range
}
```

---

### Part 2: Analysis of the "Factor of 2" in Your `calculateOptimalFocusDistance`

It's excellent that you found a factor that makes the result feel correct. However, "magic numbers" like this often hide an underlying incorrect assumption in the logic. If the phone or preview configuration changes, the magic number might fail.

Based on your screenshot, the formula is:
`val optimalDistanceMm = 2 * (focalLengthMM * averageFingerWidthMM) / (overlayToPreviewRatio * effectiveSensorDimensionForCalcMM)`

This is different from the correct physical formula, which should be:
`Distance = (Focal_Length * Real_Width * Image_Width_Pixels) / (Perceived_Width_Pixels * Sensor_Width_MM)`

You are missing the **`Image_Width_Pixels`** term in the numerator. Your code is implicitly assuming that `Image_Width_Pixels` equals `Perceived_Width_Pixels`.

The most likely reason your factor of `2` "works" is that it's compensating for a mismatch between how the `viewFinder` (preview) is displayed and how the final image is captured. This usually happens because of aspect ratio differences and the `ScaleType` (e.g., `centerCrop`).

Your current `overlayToPreviewRatio` does not account for the final image dimensions. Here is a more robust way to calculate the `targetPixelWidthOnSensor` which should eliminate the need for the factor of 2.

**Suggestion for a More Robust `calculateOptimalFocusDistance`:**

```kotlin
// In your calculateOptimalFocusDistance function, replace the middle section with this logic.
// This assumes you have the camera's final output imageSize (e.g., 4000x2250) available.

// ... inside the function ...

val overlayToPreviewRatio = overlayViewSize.width.toFloat() / viewFinderSize.width.toFloat()

val targetPixelWidthOnSensor: Float
val effectiveImageDimensionForCalc: Int
val effectiveSensorDimensionForCalc: Float

if (deviceRotation == Surface.ROTATION_0 || deviceRotation == Surface.ROTATION_180) {
    // PORTRAIT
    effectiveImageDimensionForCalc = imageSize.height // Use the pixel height of the final image
    effectiveSensorDimensionForCalc = sensorPhysicalSize.height
    targetPixelWidthOnSensor = overlayToPreviewRatio * imageSize.height.toFloat()
} else {
    // LANDSCAPE
    effectiveImageDimensionForCalc = imageSize.width
    effectiveSensorDimensionForCalc = sensorPhysicalSize.width
    targetPixelWidthOnSensor = overlayToPreviewRatio * imageSize.width.toFloat()
}

// THE CORRECT, FULL FORMULA (no factor of 2)
val optimalDistanceMm = (focalLengthMM * averageFingerWidthMM * effectiveImageDimensionForCalc) /
                        (targetPixelWidthOnSensor * effectiveSensorDimensionForCalc)

// ... continue with tolerance and min/max calculation ...
```
By including `effectiveImageDimensionForCalc` in the numerator, you are using the complete, physically accurate formula. I highly recommend trying this to see if it removes the need for your factor of 2, making your code more reliable across different devices and preview configurations.