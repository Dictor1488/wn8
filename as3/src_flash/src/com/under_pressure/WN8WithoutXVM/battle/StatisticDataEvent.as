package com.under_pressure.WN8WithoutXVM.battle
{
   import flash.events.Event;

   public class StatisticDataEvent extends Event
   {
      public static const CYCLIC_STATS_RECEIVED:String = "cyclicStatisticDataReceived";
      public static const STATS_CLEARED:String = "statisticDataCleared";

      public var vehicleID:int;

      public function StatisticDataEvent(type:String, vehicleID:int, bubbles:Boolean = false, cancelable:Boolean = false)
      {
         this.vehicleID = vehicleID;
         super(type, bubbles, cancelable);
      }

      override public function clone():Event
      {
         return new StatisticDataEvent(type, this.vehicleID, bubbles, cancelable);
      }

      override public function toString():String
      {
         return formatToString("StatisticDataEvent", "type", "vehicleID", "bubbles", "cancelable");
      }
   }
}
