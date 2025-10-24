Of course. I understand you're looking for a vertically scrolling, day-by-day schedule view, much like the Google Calendar app's agenda or schedule view. Here is a solution that achieves this by displaying dates on the left and corresponding attendance records or status (like "Absent" or "Holiday") on the right for each day.

This approach uses a `LazyColumn` to efficiently display a list of days, ensuring smooth scrolling even over a long period. Each row in the list represents a single day.

### 1. Data Models for the Schedule

First, let's define the data structures. We need a way to represent not just an attendance item, but also the status of an entire day, which could have multiple attendance records, be a holiday, or an absence.

```kotlin
import java.time.LocalDate
import java.time.LocalTime

// Represents a single check-in/check-out event
data class AttendanceEvent(
    val inTimeStamp: LocalTime,
    val outTimeStamp: LocalTime,
    val description: String // e.g., "Work Shift"
)

// Represents the status for a given day
sealed class DayStatus {
    data class Attended(val events: List<AttendanceEvent>) : DayStatus()
    data object Absent : DayStatus()
    data class Holiday(val name: String) : DayStatus()
}

// A wrapper class combining a date with its status
data class ScheduleDay(
    val date: LocalDate,
    val status: DayStatus
)
```

### 2. The Main Schedule Screen Composable

This is the top-level composable that will display the list of days. It uses a `LazyColumn` for performance, which only composes and lays out the items currently visible on the screen.

```kotlin
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp
import java.time.LocalDate
import java.time.LocalTime

@Composable
fun AttendanceScheduleScreen(scheduleDays: List<ScheduleDay>) {
    LazyColumn(
        contentPadding = PaddingValues(vertical = 16.dp)
    ) {
        items(scheduleDays) { day ->
            DayRow(day = day)
        }
    }
}
```

### 3. The `DayRow` Composable

This composable is responsible for rendering a single row in our list, which corresponds to one day. It creates the side-by-side layout with the date on the left and the day's status on the right.

```kotlin
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.time.format.TextStyle
import java.util.Locale

@Composable
fun DayRow(day: ScheduleDay) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.Top
    ) {
        // Left side: Date
        Column(
            modifier = Modifier.width(60.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = day.date.dayOfWeek.getDisplayName(TextStyle.SHORT, Locale.getDefault()),
                style = MaterialTheme.typography.bodySmall
            )
            Text(
                text = day.date.dayOfMonth.toString(),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
        }

        // Spacer
        Spacer(modifier = Modifier.width(16.dp))

        // Right side: Status (Attendance, Absent, or Holiday)
        Column(modifier = Modifier.weight(1f)) {
            when (val status = day.status) {
                is DayStatus.Attended -> {
                    // Display each attendance event for the day
                    status.events.forEach { event ->
                        AttendanceEventCard(event = event)
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }
                is DayStatus.Absent -> {
                    Text(text = "Absent", color = Color.Red)
                }
                is DayStatus.Holiday -> {
                    Text(text = "Holiday: ${status.name}", color = Color.Gray)
                }
            }
        }
    }
}
```

### 4. The `AttendanceEventCard` Composable

This composable renders a single attendance event in a visually appealing card, showing the in/out times and description.

```kotlin
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import java.time.format.DateTimeFormatter

@Composable
fun AttendanceEventCard(event: AttendanceEvent) {
    val timeFormatter = DateTimeFormatter.ofPattern("hh:mm a")

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
    ) {
        Row(modifier = Modifier.padding(12.dp)) {
            // You can add a decorative color bar here if you like
            Box(
                modifier = Modifier
                    .width(4.dp)
                    .fillMaxHeight()
                    .background(MaterialTheme.colorScheme.primary)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Text(
                    text = event.description,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "${event.inTimeStamp.format(timeFormatter)} - ${event.outTimeStamp.format(timeFormatter)}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.Gray
                )
            }
        }
    }
}
```

### How to Use It in Your App

You can now put everything together in your main screen composable. You would fetch your attendance data and transform it into a `List<ScheduleDay>`.

```kotlin
@Composable
fun MyAttendanceRecordScreen() {
    // --- Sample Data ---
    // In a real app, you would generate this list from your database or API
    // for a given date range.
    val scheduleData = listOf(
        ScheduleDay(
            date = LocalDate.now(),
            status = DayStatus.Attended(events = listOf(
                AttendanceEvent(LocalTime.of(9, 5), LocalTime.of(12, 30), "Morning Shift"),
                AttendanceEvent(LocalTime.of(13, 15), LocalTime.of(17, 45), "Afternoon Shift")
            ))
        ),
        ScheduleDay(
            date = LocalDate.now().minusDays(1),
            status = DayStatus.Absent
        ),
        ScheduleDay(
            date = LocalDate.now().minusDays(2),
            status = DayStatus.Attended(events = listOf(
                AttendanceEvent(LocalTime.of(10, 0), LocalTime.of(18, 0), "Full Day")
            ))
        ),
        ScheduleDay(
            date = LocalDate.now().minusDays(3),
            status = DayStatus.Holiday(name = "Public Holiday")
        ),
        ScheduleDay(
            date = LocalDate.now().minusDays(4),
            status = DayStatus.Attended(events = listOf(
                AttendanceEvent(LocalTime.of(8, 30), LocalTime.of(12, 30), "Morning Work")
            ))
        )
    )
    // --- End Sample Data ---

    AttendanceScheduleScreen(scheduleDays = scheduleData)
}
```

This structure gives you the exact Google Calendar-style schedule view you wanted, providing a clear, scrollable history of attendance records, absences, and holidays.