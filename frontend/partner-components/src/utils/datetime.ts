/* Conversion helpers between Luxon and Internationalized Date */

import { DateTime } from 'luxon'
import { CalendarDate, CalendarDateTime, ZonedDateTime, type DateValue } from '@internationalized/date'

export function toDateValue(dt: DateTime, includeTime = false): DateValue {
  if (includeTime) {
    const zone = dt.zoneName
    if (zone) {
      return new ZonedDateTime(
        dt.year, dt.month, dt.day,
        zone,
        dt.offset * 60 * 1000, // Luxon offset is minutes, ZonedDateTime wants ms
        dt.hour, dt.minute, dt.second, dt.millisecond,
      )
    }
    return new CalendarDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.millisecond)
  }
  return new CalendarDate(dt.year, dt.month, dt.day)
}

export { toDateValue as toInternationalizedDateValue }

export function toDateTime(date: DateValue, zone?: string): DateTime {
  if ('hour' in date) {
    if ('timeZone' in date) {
      return DateTime.fromJSDate(date.toDate(), { zone: date.timeZone })
    }
    return DateTime.fromObject(
      { year: date.year, month: date.month, day: date.day, hour: date.hour, minute: date.minute, second: date.second, millisecond: date.millisecond },
      zone ? { zone } : undefined,
    )
  }
  return DateTime.fromObject(
    { year: date.year, month: date.month, day: date.day },
    zone ? { zone } : undefined,
  )
}

export { toDateTime as toLuxonDateTime }