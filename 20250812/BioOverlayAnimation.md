Of course. This is a fantastic and much more sophisticated UX concept. The two-layer system (a static base layer and a dynamic animation layer) provides excellent visual feedback and makes the state transitions feel much more deliberate and polished.

Here is the breakdown of the updates and the final code.

### Summary of Updates

1.  **Dual `Paint` System:**
    *   The view will now manage two `Paint` objects:
        *   `baseBorderPaint`: This is the primary line. Its stroke width will animate between a "thin" and "thick" value. Its style can be solid or dashed.
        *   `animationBorderPaint`: This is the secondary, always-thick line used *only* for the `PRE_AUTO_CAPTURE` and `AUTO_CAPTURE_SUCCESS` states. It will fade in/out and perform the progress/looping animations.

2.  **New Animation Properties & Animators:**
    *   **Stroke Width Animation:** A `ValueAnimator` will smoothly change the `strokeWidth` of the `baseBorderPaint` to create the "thin-to-thick" and "thick-to-thin" effects.
    *   **Alpha (Fade) Animation:** A `ValueAnimator` will control the alpha (opacity) of the `animationBorderPaint`, allowing it to fade in and out gracefully.
    *   **Updated State Logic:** The `setState` and transition methods are completely rewritten to orchestrate these new animations.

3.  **Revised `onDraw()` Logic:**
    *   The `onDraw` method is now more complex. It will first draw the base line with its current stroke width and style.
    *   Then, *if* the state requires it, it will draw the second animation line on top, using its own path segment and alpha value.

4.  **Refined "Chasing Looper" Animation:**
    *   The `AUTO_CAPTURE_SUCCESS` animation is implemented exactly as you described: a thick line segment of a fixed length (e.g., 90%) that continuously rotates around the thin base line.

5.  **Elegant Transitions:**
    *   The new `animateVisualTransition` function acts as an orchestrator. It uses `AnimatorSet` to play multiple animations simultaneously (e.g., changing stroke width while also fading out the animation line), creating a seamless and professional feel.

---

### The Final Updated Code

Here is the complete, final version of the `BiometricOverlayView.kt` file incorporating all these changes.

```kotlin
package `in`.gov.uidai.capture.ui.camera.view

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.AnimatorSet
import android.animation.ArgbEvaluator
import android.animation.ValueAnimator
import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PathMeasure
import android.graphics.PorterDuff
import android.graphics.PorterDuffXfermode
import android.graphics.RectF
import android.util.AttributeSet
import android.util.TypedValue
import android.view.View
import android.view.animation.AccelerateDecelerateInterpolator
import android.view.animation.LinearInterpolator
import androidx.annotation.ColorRes
import androidx.core.content.ContextCompat
import `in`.gov.uidai.capture.R

class BiometricOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    // --- State Management ---
    sealed class State(
        @ColorRes val colorRes: Int,
        val hasThinBase: Boolean // New property to define the base layer
    ) {
        object INITIAL : State(android.R.color.white, false)
        object WARNING : State(R.color.ui_red, false)
        object PRE_AUTO_CAPTURE : State(android.R.color.white, true)
        object AUTO_CAPTURE_SUCCESS : State(R.color.ui_green, true)
        object SUCCESS : State(R.color.ui_green, false)
        object FAILURE : State(R.color.ui_red, false)
    }

    // --- Configuration ---
    companion object {
        private const val RECT_HEIGHT_F = 80f
        private const val SEMICIRCLE_RADIUS_F = 85f
        private const val COLOR_ANIMATION_DURATION = 300L
        private const val TRANSITION_DURATION = 400L
        private const val PROGRESS_ANIMATION_DURATION = 1000L
        private const val LOOP_ANIMATION_DURATION = 1500L
        private const val CHASING_LOOP_SEGMENT_PROPORTION = 0.8f // 80% of path
        private const val DASH_LENGTH = 30f
        private const val DASH_GAP = 20f
    }

    // --- Sizing ---
    private val thickStrokeWidth = dpToPx(6f)
    private val thinStrokeWidth = dpToPx(2f)

    // --- State & Drawing Objects ---
    private var currentState: State = State.INITIAL
    private var currentColor: Int = ContextCompat.getColor(context, currentState.colorRes)
    private val path = Path()
    private val segmentPath = Path()
    private val pathMeasure = PathMeasure()

    // --- NEW: Dual Paint System ---
    private val baseBorderPaint = createPaint()
    private val animationBorderPaint = createPaint()
    private val backgroundPaint = Paint().apply {
        style = Paint.Style.FILL
        color = ContextCompat.getColor(context, R.color.bg_biometric_overlay)
    }
    private val cutoutPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
        xfermode = PorterDuffXfermode(PorterDuff.Mode.CLEAR)
    }

    // --- Animation Properties ---
    private var currentProgress = 0f
    private var loopProgress = 0f
    private var animatedDashGap = DASH_GAP
    private var animationLineAlpha = 0 // Alpha for the top animation layer

    // --- Animators ---
    private var currentAnimatorSet: AnimatorSet? = null
    private val loopAnimator = ValueAnimator.ofFloat(0f, 1f)
    private val dashAnimator = ValueAnimator.ofFloat(0f, -(DASH_LENGTH + DASH_GAP))

    init {
        setupAnimators()
        // Start in the initial state without animations
        baseBorderPaint.strokeWidth = thickStrokeWidth
        animationBorderPaint.strokeWidth = thickStrokeWidth
        animatedDashGap = DASH_GAP
        setState(State.INITIAL, animate = false)
    }

    private fun createPaint() = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }
    
    private fun setupAnimators() {
        loopAnimator.apply {
            duration = LOOP_ANIMATION_DURATION
            interpolator = LinearInterpolator()
            repeatCount = ValueAnimator.INFINITE
            addUpdateListener { loopProgress = it.animatedValue as Float; invalidate() }
        }
        dashAnimator.apply {
            duration = 800
            interpolator = LinearInterpolator()
            repeatCount = ValueAnimator.INFINITE
            addUpdateListener { invalidate() }
        }
    }

    fun setState(newState: State, animate: Boolean = true) {
        if (currentState == newState) return
        val oldState = currentState
        currentState = newState

        currentAnimatorSet?.cancel()
        animateColor(newState.colorRes, animate)

        if (animate) {
            animateVisualTransition(oldState, newState)
        } else {
            // Jump to the final state without transitions
            baseBorderPaint.strokeWidth = if (newState.hasThinBase) thinStrokeWidth else thickStrokeWidth
            animatedDashGap = if (newState is State.INITIAL) DASH_GAP else 0f
            animationLineAlpha = if (newState.hasThinBase) 255 else 0
            
            loopAnimator.cancel()
            dashAnimator.cancel()
            if(newState is State.INITIAL) dashAnimator.start()
            if(newState is State.AUTO_CAPTURE_SUCCESS) loopAnimator.start()
            
            invalidate()
        }
    }

    private fun animateVisualTransition(fromState: State, toState: State) {
        val animatorList = mutableListOf<Animator>()

        // 1. Animate the Base Line (Stroke Width and Dash Style)
        val targetStrokeWidth = if (toState.hasThinBase) thinStrokeWidth else thickStrokeWidth
        if (baseBorderPaint.strokeWidth != targetStrokeWidth) {
            animatorList.add(ValueAnimator.ofFloat(baseBorderPaint.strokeWidth, targetStrokeWidth).apply {
                addUpdateListener { baseBorderPaint.strokeWidth = it.animatedValue as Float; invalidate() }
            })
        }
        
        val targetDashGap = if (toState is State.INITIAL) DASH_GAP else 0f
        if (animatedDashGap != targetDashGap) {
            animatorList.add(ValueAnimator.ofFloat(animatedDashGap, targetDashGap).apply {
                addUpdateListener { animatedDashGap = it.animatedValue as Float }
            })
        }

        // 2. Animate the Animation Line (Alpha and Progress)
        val targetAlpha = if (toState.hasThinBase) 255 else 0
        if (animationLineAlpha != targetAlpha) {
            animatorList.add(ValueAnimator.ofInt(animationLineAlpha, targetAlpha).apply {
                addUpdateListener { animationLineAlpha = it.animatedValue as Int }
            })
        }

        // Handle case where an animation is reversing (e.g., Pre-Capture -> Warning)
        if (fromState is State.PRE_AUTO_CAPTURE && !toState.hasThinBase) {
            animatorList.add(ValueAnimator.ofFloat(currentProgress, 0f).apply {
                addUpdateListener { currentProgress = it.animatedValue as Float }
            })
        }
        
        currentAnimatorSet = AnimatorSet().apply {
            playTogether(animatorList)
            duration = TRANSITION_DURATION
            interpolator = AccelerateDecelerateInterpolator()
            addListener(object : AnimatorListenerAdapter() {
                override fun onAnimationEnd(animation: Animator) {
                    // Settle into the new state's continuous animation
                    postTransitionUpdate(toState)
                }
                override fun onAnimationCancel(animation: Animator) {
                    postTransitionUpdate(toState)
                }
            })
            start()
        }
    }

    /** Called after a transition finishes to start the new state's persistent animation. */
    private fun postTransitionUpdate(state: State) {
        currentAnimatorSet = null
        loopAnimator.cancel()
        dashAnimator.cancel()
        
        when (state) {
            is State.INITIAL -> {
                dashAnimator.start()
            }
            is State.PRE_AUTO_CAPTURE -> {
                // Start the 0-100% progress animation
                ValueAnimator.ofFloat(0f, 1f).apply {
                    duration = PROGRESS_ANIMATION_DURATION
                    addUpdateListener { currentProgress = it.animatedValue as Float; invalidate() }
                    start()
                }
            }
            is State.AUTO_CAPTURE_SUCCESS -> {
                loopAnimator.start()
            }
            else -> { // Warning, Success, Failure have no continuous animations
                invalidate()
            }
        }
    }
    
    private fun animateColor(@ColorRes colorRes: Int, animate: Boolean) {
        val targetColor = ContextCompat.getColor(context, colorRes)
        if (currentColor == targetColor) return
        ValueAnimator.ofObject(ArgbEvaluator(), currentColor, targetColor).apply {
            duration = if (animate) COLOR_ANIMATION_DURATION else 0
            addUpdateListener {
                currentColor = it.animatedValue as Int
                baseBorderPaint.color = currentColor
                animationBorderPaint.color = currentColor
                invalidate()
            }
            start()
        }
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        configurePath(w, h)
        pathMeasure.setPath(path, false)
    }

    private fun configurePath(w: Int, h: Int) {
        path.reset()
        val centerX = w / 2f; val centerY = h / 2f
        val rectHalfHeightPx = dpToPx(RECT_HEIGHT_F / 2); val radiusPx = dpToPx(SEMICIRCLE_RADIUS_F)
        val topArcRect = RectF(centerX - radiusPx, centerY - rectHalfHeightPx - radiusPx, centerX + radiusPx, centerY - rectHalfHeightPx + radiusPx)
        val bottomArcRect = RectF(centerX - radiusPx, centerY + rectHalfHeightPx - radiusPx, centerX + radiusPx, centerY + rectHalfHeightPx + radiusPx)
        path.moveTo(centerX - radiusPx, centerY - rectHalfHeightPx)
        path.arcTo(topArcRect, 180f, 180f)
        path.lineTo(centerX + radiusPx, centerY + rectHalfHeightPx)
        path.arcTo(bottomArcRect, 0f, 180f)
        path.close()
    }

    @SuppressLint("DrawAllocation")
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), backgroundPaint)
        canvas.drawPath(path, cutoutPaint)
        
        // --- 1. Draw the Base Line ---
        baseBorderPaint.pathEffect = if (animatedDashGap > 0.1f) {
            DashPathEffect(floatArrayOf(DASH_LENGTH, animatedDashGap), dashAnimator.animatedValue as? Float ?: 0f)
        } else {
            null
        }
        canvas.drawPath(path, baseBorderPaint)

        // --- 2. Draw the Animation Line on top (if visible) ---
        if (animationLineAlpha > 0) {
            animationBorderPaint.alpha = animationLineAlpha
            segmentPath.reset()
            val pathLength = pathMeasure.length
            if (pathLength <= 0) return

            when (currentState) {
                is State.PRE_AUTO_CAPTURE -> {
                    pathMeasure.getSegment(0f, pathLength * currentProgress, segmentPath, true)
                }
                is State.AUTO_CAPTURE_SUCCESS -> {
                    val segmentLength = pathLength * CHASING_LOOP_SEGMENT_PROPORTION
                    val startD = pathLength * loopProgress
                    val stopD = startD + segmentLength
                    if (stopD > pathLength) {
                        pathMeasure.getSegment(startD, pathLength, segmentPath, true)
                        val overflowPath = Path()
                        pathMeasure.getSegment(0f, stopD - pathLength, overflowPath, true)
                        segmentPath.addPath(overflowPath)
                    } else {
                        pathMeasure.getSegment(startD, stopD, segmentPath, true)
                    }
                }
                else -> { /* No animation line for other states */ }
            }
            canvas.drawPath(segmentPath, animationBorderPaint)
        }
    }
    
    private fun dpToPx(dp: Float): Float {
        return TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, dp, resources.displayMetrics)
    }

    override fun onDetachedFromWindow() {
        super.onDetachedFromWindow()
        currentAnimatorSet?.cancel()
        loopAnimator.cancel()
        dashAnimator.cancel()
    }
}
```