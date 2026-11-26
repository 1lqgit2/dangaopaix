using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class TimeUtil : MonoBehaviour {
    public static string RemainTimeToString(float remainTime) {
        TimeSpan timeSpan = TimeSpan.FromSeconds(remainTime);
        return string.Format("{0:D1}小时{1:D2}分{2:D2}秒", timeSpan.Hours, timeSpan.Minutes, timeSpan.Seconds);
    }
    public static string RemainTimeToString2(float remainTime) {
        TimeSpan timeSpan = TimeSpan.FromSeconds(remainTime);
        return string.Format("{0:D1}:{1:D2}:{2:D2}", timeSpan.Hours, timeSpan.Minutes, timeSpan.Seconds);
    }
    public static string RemainTimeToString3(float remainTime) {
        TimeSpan timeSpan = TimeSpan.FromSeconds(remainTime);
        return string.Format("{0:D1}小时{1:D2}分", timeSpan.Hours, timeSpan.Minutes);
    }
    public static string TimeToString(float inputTime, TimeFommat timeFommat = TimeFommat.Keyword)
    {
        TimeSpan timeSpan = TimeSpan.FromSeconds(inputTime);
        if (timeFommat == TimeFommat.Keyword)
        {
            if (timeSpan.TotalDays >= 1)
            {
                return string.Format("{0:D1}天{1:D2}小时{2:D2}分", timeSpan.Days, timeSpan.Hours, timeSpan.Minutes);
            }
            else if (timeSpan.TotalHours >= 1)
            {
                if (timeSpan.Seconds == 0)
                {
                    if (timeSpan.Minutes == 0)
                        return string.Format("{0:D1}小时", timeSpan.Hours);
                    else
                        return string.Format("{0:D1}小时{1:D2}分", timeSpan.Hours, timeSpan.Minutes);
                }
                return string.Format("{0:D1}小时{1:D2}分{2:D2}秒", timeSpan.Hours, timeSpan.Minutes, timeSpan.Seconds);
            }
            else if (timeSpan.TotalMinutes >= 1)
            {
                if (timeSpan.Seconds == 0)
                    return string.Format("{0:D1}分", timeSpan.Minutes);
                return string.Format("{0:D1}分{1:D2}秒", timeSpan.Minutes, timeSpan.Seconds);
            }
            if (timeSpan.TotalSeconds < 10)
            {
                return string.Format("{0:D1}秒", timeSpan.Seconds);
            }
            return string.Format("{0:D2}秒", timeSpan.Seconds);
        }
        else if (timeFommat == TimeFommat.Symbol)
        {
            if (timeSpan.TotalDays >= 1)
            {
                return string.Format("{0:D1}: {1:D2}: {2:D2}", timeSpan.Days, timeSpan.Hours, timeSpan.Minutes);
            }
            else if (timeSpan.TotalHours >= 1)
            {
                if (timeSpan.Seconds == 0)
                {
                    if (timeSpan.Minutes == 0)
                        return string.Format("{0:D1}", timeSpan.Hours);
                    else
                        return string.Format("{0:D1}: {1:D2}", timeSpan.Hours, timeSpan.Minutes);
                }
                return string.Format("{0:D1}: {1:D2}: {2:D2}", timeSpan.Hours, timeSpan.Minutes, timeSpan.Seconds);
            }
            else if (timeSpan.TotalMinutes >= 1)
            {
                if (timeSpan.Seconds == 0)
                    return string.Format("{0:D1}", timeSpan.Minutes);
                return string.Format("{0:D1}: {1:D2}", timeSpan.Minutes, timeSpan.Seconds);
            }
            if (timeSpan.TotalSeconds < 10)
            {
                return string.Format("{0:D1}", timeSpan.Seconds);
            }
            return string.Format("{0:D2}", timeSpan.Seconds);
        }
        return ConstantValue.STR_BLANK;
    }

    public static string ConvertFloatToString(float value, string format = "{0:0.00}") {
        if (value == (int)value) return value.ToString();
        return string.Format(format, value);
    }
}

public enum TimeFommat
{
    Keyword,
    Symbol
}
