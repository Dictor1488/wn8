package com.under_pressure.WN8WithoutXVM.battle
{
   import flash.display.Sprite;
   import flash.utils.Dictionary;

   public class StatisticDataCache extends Sprite
   {
      private static var _instance:StatisticDataCache = null;

      private var _cache:Dictionary;
      private var _mapVehicleID:Dictionary;
      private var _mapAccountToVehicle:Dictionary;
      private var _isDisposed:Boolean;

      public function StatisticDataCache()
      {
         super();
         this._cache = new Dictionary();
         this._mapVehicleID = new Dictionary();
         this._mapAccountToVehicle = new Dictionary();
         this._isDisposed = false;
         _instance = this;
      }

      public static function getInstance():StatisticDataCache
      {
         if (_instance == null)
         {
            _instance = new StatisticDataCache();
         }
         return _instance;
      }

      public function addStatsData(vehicleID:int, data:Object):void
      {
         if (this._isDisposed || !data) return;

         this._cache[vehicleID] = data;

         if (data.hasOwnProperty("accountDBID"))
         {
            var accountID:int = int(data.accountDBID);
            this._mapVehicleID[accountID] = vehicleID;
            this._mapAccountToVehicle[accountID] = vehicleID;
         }

         dispatchEvent(new StatisticDataEvent(StatisticDataEvent.CYCLIC_STATS_RECEIVED, vehicleID));
      }

      public function getStatsData(vehicleID:int):Object
      {
         if (this._isDisposed) return null;
         return this._cache[vehicleID];
      }

      public function getStatsDataByAccountID(accountID:int):Object
      {
         if (this._isDisposed) return null;

         var vehicleID:int = int(this._mapVehicleID[accountID]);
         if (vehicleID)
         {
            return this.getStatsData(vehicleID);
         }
         return null;
      }

      public function getVehicleIDByAccountID(accountID:int):int
      {
         if (this._isDisposed) return 0;
         return int(this._mapAccountToVehicle[accountID]);
      }

      public function hasStatsData(vehicleID:int):Boolean
      {
         if (this._isDisposed) return false;
         return this._cache[vehicleID] != null;
      }

      public function hasStatsDataByAccountID(accountID:int):Boolean
      {
         if (this._isDisposed) return false;
         var vehicleID:int = int(this._mapVehicleID[accountID]);
         return vehicleID > 0 && this._cache[vehicleID] != null;
      }

      public function get mapVehicleID():Dictionary
      {
         return this._mapVehicleID;
      }

      public function getAllVehicleIDs():Vector.<int>
      {
         var result:Vector.<int> = new Vector.<int>();
         if (this._isDisposed) return result;

         for (var key:* in this._cache)
         {
            result.push(int(key));
         }
         return result;
      }

      public function clear():void
      {
         if (this._isDisposed) return;

         for (var key:* in this._cache)
         {
            delete this._cache[key];
         }
         for (var key2:* in this._mapVehicleID)
         {
            delete this._mapVehicleID[key2];
         }
         for (var key3:* in this._mapAccountToVehicle)
         {
            delete this._mapAccountToVehicle[key3];
         }
      }

      public function remove():void
      {
         this._isDisposed = true;
         this.clear();
         this._cache = null;
         this._mapVehicleID = null;
         this._mapAccountToVehicle = null;
         _instance = null;
      }
   }
}
