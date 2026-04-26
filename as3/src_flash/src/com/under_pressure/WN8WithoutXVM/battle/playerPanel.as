package com.under_pressure.WN8WithoutXVM.battle
{
   import flash.display.DisplayObject;
   import flash.events.Event;
   import flash.filters.DropShadowFilter;
   import flash.geom.ColorTransform;
   import flash.text.AntiAliasType;
   import flash.text.TextField;
   import flash.text.TextFieldAutoSize;
   import flash.text.TextFormat;
   import flash.utils.Dictionary;
   import com.under_pressure.WN8WithoutXVM.injector.BattleDisplayable;
   import com.under_pressure.WN8WithoutXVM.utils.Utils;
   import net.wg.data.constants.generated.PLAYERS_PANEL_STATE;
   import net.wg.gui.battle.components.BattleAtlasSprite;
   import net.wg.gui.battle.random.views.BattlePage;
   import net.wg.gui.battle.views.stats.fullStats.FullStatsTableBase;
   import scaleform.gfx.TextFieldEx;

   public class playerPanel extends BattleDisplayable
   {
      private static const POOL_SIZE:int = 64;
      private static const TYPE_PP:String = "pp";
      private static const TAB_NUM_ROWS:int = 15;
      private static const TAB_OVERLAY_OFFSET_X:Number = 4;

      private var _textFieldPool:Vector.<TextField>;
      private var _defaultTextFormat:TextFormat;

      private var _containers:Dictionary;
      private var _vehicleTextFields:Dictionary;
      private var _tabOverlayTextFields:Vector.<TextField>;

      private var _cachedShadows:Dictionary;
      private var _statsCacheMgr:StatisticDataCache;

      private var _eventListeners:Vector.<BattleAtlasSprite>;
      private var _currentPanelState:int;
      private var _isDisposed:Boolean;

      public var flashLogS:Function;

      public function playerPanel()
      {
         super();
         name = "playerPanel";

         this._textFieldPool = new Vector.<TextField>();
         this._defaultTextFormat = new TextFormat("$UniversCondC", 14, 0xFFFFFF, false, false, false, "", "", "left", 0, 0, 0, 0);

         this._containers = new Dictionary();
         this._vehicleTextFields = new Dictionary();
         this._tabOverlayTextFields = new Vector.<TextField>(TAB_NUM_ROWS * 2, true);
         this._cachedShadows = new Dictionary();
         this._eventListeners = new Vector.<BattleAtlasSprite>();
         this._currentPanelState = -1;
         this._isDisposed = false;

         this._statsCacheMgr = StatisticDataCache.getInstance();
         this._statsCacheMgr.addEventListener(StatisticDataEvent.CYCLIC_STATS_RECEIVED, this.onStatsReceived, false, 0, true);

         this.initializeTextFieldPool();
      }

      private function initializeTextFieldPool():void
      {
         for (var i:int = 0; i < POOL_SIZE; i++)
         {
            this._textFieldPool.push(this.createPooledTextField());
         }
      }

      private function createPooledTextField():TextField
      {
         var tf:TextField = new TextField();
         TextFieldEx.setNoTranslate(tf, true);
         tf.defaultTextFormat = this._defaultTextFormat;
         tf.mouseEnabled = false;
         tf.background = false;
         tf.backgroundColor = 0;
         tf.embedFonts = true;
         tf.multiline = false;
         tf.selectable = false;
         tf.tabEnabled = false;
         tf.antiAliasType = AntiAliasType.ADVANCED;
         return tf;
      }

      private function getTextFieldFromPool():TextField
      {
         if (this._textFieldPool.length > 0)
         {
            return this._textFieldPool.pop();
         }
         return this.createPooledTextField();
      }

      private function returnTextFieldToPool(tf:TextField):void
      {
         if (!tf || this._isDisposed) return;

         tf.text = "";
         tf.htmlText = "";
         tf.filters = null;
         tf.alpha = 1;
         tf.visible = true;

         var ct:ColorTransform = new ColorTransform();
         tf.transform.colorTransform = ct;

         if (tf.parent)
         {
            tf.parent.removeChild(tf);
         }

         if (this._textFieldPool && this._textFieldPool.length < POOL_SIZE)
         {
            this._textFieldPool.push(tf);
         }
      }

      private function getCachedShadow(shadowConfig:Object):DropShadowFilter
      {
         if (!shadowConfig) return null;
         var key:String = String(shadowConfig.distance) + "_" + String(shadowConfig.angle) + "_" +
                          String(shadowConfig.color) + "_" + String(shadowConfig.alpha) + "_" +
                          String(shadowConfig.size) + "_" + String(shadowConfig.strength);
         if (!this._cachedShadows[key])
         {
            this._cachedShadows[key] = Utils.getDropShadowFilter(
               shadowConfig.distance, shadowConfig.angle, shadowConfig.color,
               shadowConfig.alpha, shadowConfig.size, shadowConfig.strength
            );
         }
         return this._cachedShadows[key] as DropShadowFilter;
      }

      private function onStatsReceived(event:StatisticDataEvent):void
      {
         if (this._isDisposed) return;
         var vehicleID:int = event.vehicleID;
         var data:Object = this._statsCacheMgr.getStatsData(vehicleID);
         if (!data) return;
         for (var containerName:String in this._containers)
         {
            this.updateVehicleTextField(containerName, vehicleID, data);
         }
      }

      private function updateVehicleTextField(containerName:String, vehicleID:int, data:Object):void
      {
         var container:Object = this._containers[containerName];
         if (!container) return;

         var textKey:String = container.textKey || containerName;
         var isEnemy:Boolean = this.isPPEnemy(vehicleID);
         var side:String = isEnemy ? "right" : "left";
         var fullKey:String = textKey + "_" + side;

         var vehicleFields:Dictionary = this._vehicleTextFields[containerName] as Dictionary;
         if (!vehicleFields)
         {
            vehicleFields = new Dictionary();
            this._vehicleTextFields[containerName] = vehicleFields;
         }

         if (!vehicleFields[vehicleID])
         {
            this.createPPTextField(containerName, vehicleID, container);
         }

         var tf:TextField = vehicleFields[vehicleID] as TextField;
         if (!tf) return;

         var text:String = "";
         if (data.hasOwnProperty(fullKey))
         {
            text = String(data[fullKey]);
         }
         else if (data.hasOwnProperty(textKey))
         {
            text = String(data[textKey]);
         }

         if (text.length > 0)
         {
            tf.htmlText = text;
            tf.visible = true;
         }
      }

      public function as_setStatsData(vehicleID:int, data:Object):void
      {
         if (!data || this._isDisposed) return;
         try
         {
            this._statsCacheMgr.addStatsData(vehicleID, data);
         }
         catch (e:Error)
         {
            this.logError("as_setStatsData: " + e.message);
         }
      }

      public function as_create(containerName:String, config:Object):void
      {
         if (!containerName || containerName.length == 0 || !config || this._isDisposed) return;
         try
         {
            this._containers[containerName] = config;
            this._vehicleTextFields[containerName] = new Dictionary();
         }
         catch (e:Error)
         {
            this.logError("as_create: " + e.message);
         }
      }

      public function as_update(containerName:String, data:Object):void
      {
         if (!containerName || !data || this._isDisposed) return;
         if (!data.hasOwnProperty("vehicleID")) return;
         try
         {
            var vehicleID:int = int(data.vehicleID);
            var container:Object = this._containers[containerName];
            if (!container) return;

            var vehicleFields:Dictionary = this._vehicleTextFields[containerName] as Dictionary;
            if (!vehicleFields)
            {
               vehicleFields = new Dictionary();
               this._vehicleTextFields[containerName] = vehicleFields;
            }

            if (!vehicleFields[vehicleID])
            {
               this.createPPTextField(containerName, vehicleID, container);
            }

            var tf:TextField = vehicleFields[vehicleID] as TextField;
            if (tf && data.hasOwnProperty("text"))
            {
               tf.htmlText = String(data.text);
               tf.visible = true;
            }
         }
         catch (e:Error)
         {
            this.logError("as_update: " + e.message);
         }
      }

      public function as_delete(containerName:String):void
      {
         if (!containerName || this._isDisposed) return;
         try
         {
            var vehicleFields:Dictionary = this._vehicleTextFields[containerName] as Dictionary;
            if (vehicleFields)
            {
               for (var vehicleId:* in vehicleFields)
               {
                  var tf:TextField = vehicleFields[vehicleId] as TextField;
                  if (tf)
                  {
                     this.returnTextFieldToPool(tf);
                  }
               }
            }
            delete this._containers[containerName];
            delete this._vehicleTextFields[containerName];
         }
         catch (e:Error)
         {
            this.logError("as_delete: " + e.message);
         }
      }

      public function as_hasOwnProperty(containerName:String):Boolean
      {
         return containerName ? this._containers[containerName] != null : false;
      }

      public function as_updatePosition(containerName:String, vehicleID:int):void
      {
         if (!containerName || this._isDisposed) return;
         var container:Object = this._containers[containerName];
         if (!container) return;
         try
         {
            var vehicleFields:Dictionary = this._vehicleTextFields[containerName] as Dictionary;
            if (!vehicleFields || !vehicleFields[vehicleID]) return;
            var tf:TextField = vehicleFields[vehicleID] as TextField;
            if (!tf) return;
            this.updatePPTextFieldPosition(containerName, vehicleID, tf, container);
         }
         catch (e:Error)
         {
            this.logError("as_updatePosition: " + e.message);
         }
      }

      public function as_updateAllPositions():void
      {
         if (this._isDisposed) return;
         for (var containerName:String in this._containers)
         {
            var container:Object = this._containers[containerName];
            var vehicleFields:Dictionary = this._vehicleTextFields[containerName] as Dictionary;
            if (vehicleFields)
            {
               for (var vehicleId:* in vehicleFields)
               {
                  var tf:TextField = vehicleFields[vehicleId] as TextField;
                  if (tf)
                  {
                     this.updatePPTextFieldPosition(containerName, int(vehicleId), tf, container);
                  }
               }
            }
         }
      }

      public function as_setPanelState(state:int):void
      {
         if (this._currentPanelState == state || this._isDisposed) return;
         this._currentPanelState = state;
         this.as_updateAllPositions();
      }

      public function as_clearCache():void
      {
         if (this._statsCacheMgr)
         {
            this._statsCacheMgr.clear();
         }
      }

      public function as_getPPListItem(vehicleID:int):*
      {
         return this.getPPListItem(vehicleID);
      }

      public function as_getPlayersPanel():*
      {
         try
         {
            var page:BattlePage = this.battlePage as BattlePage;
            if (page && page.playersPanel)
            {
               return page.playersPanel;
            }
         }
         catch (e:Error)
         {
            this.logError("as_getPlayersPanel: " + e.message);
         }
         return null;
      }

      public function getPPListItem(vehicleID:int):*
      {
         try
         {
            var page:BattlePage = this.battlePage as BattlePage;
            if (!page || !page.playersPanel) return null;
            var listRight:* = page.playersPanel.listRight;
            if (listRight)
            {
               var holderRight:* = listRight.getHolderByVehicleID(vehicleID);
               if (holderRight) return this.getListItemFromHolder(holderRight);
            }
            var listLeft:* = page.playersPanel.listLeft;
            if (listLeft)
            {
               var holderLeft:* = listLeft.getHolderByVehicleID(vehicleID);
               if (holderLeft) return this.getListItemFromHolder(holderLeft);
            }
         }
         catch (e:Error)
         {
            this.logError("getPPListItem: " + e.message);
         }
         return null;
      }

      private function getListItemFromHolder(holder:*):*
      {
         if (!holder) return null;
         try
         {
            if (holder.hasOwnProperty("getListItem")) return holder.getListItem();
            if (holder.hasOwnProperty("_listItem")) return holder["_listItem"];
         }
         catch (e:Error)
         {
            this.logError("getListItemFromHolder: " + e.message);
         }
         return null;
      }

      private function isPPEnemy(vehicleID:int):Boolean
      {
         try
         {
            var page:BattlePage = this.battlePage as BattlePage;
            if (!page || !page.playersPanel) return false;
            var listRight:* = page.playersPanel.listRight;
            if (listRight)
            {
               var holder:* = listRight.getHolderByVehicleID(vehicleID);
               return holder != null;
            }
         }
         catch (e:Error) { }
         return false;
      }

      private function createPPTextField(containerName:String, vehicleID:int, container:Object):void
      {
         try
         {
            var listItem:* = this.getPPListItem(vehicleID);
            if (!listItem) return;

            var isEnemy:Boolean = this.isPPEnemy(vehicleID);
            var posConfig:Object = container[isEnemy ? "right" : "left"];
            var shadowConfig:Object = container["shadow"];

            var tf:TextField = this.getTextFieldFromPool();
            var childName:String = container["child"];

            if (childName && listItem.hasOwnProperty(childName))
            {
               var childElement:DisplayObject = listItem[childName] as DisplayObject;
               if (childElement)
               {
                  var childIndex:int = listItem.getChildIndex(childElement);
                  listItem.addChildAt(tf, childIndex + 1);
               }
               else
               {
                  listItem.addChild(tf);
               }
            }
            else
            {
               listItem.addChild(tf);
            }

            tf.width = posConfig.width || 80;
            tf.height = posConfig.height || 20;
            this.applyAutoSize(tf, posConfig.align);

            if (shadowConfig)
            {
               tf.filters = [this.getCachedShadow(shadowConfig)];
            }

            this.updatePPTextFieldPosition(containerName, vehicleID, tf, container);

            var vehicleFields:Dictionary = this._vehicleTextFields[containerName] as Dictionary;
            if (!vehicleFields)
            {
               vehicleFields = new Dictionary();
               this._vehicleTextFields[containerName] = vehicleFields;
            }
            vehicleFields[vehicleID] = tf;
         }
         catch (e:Error)
         {
            this.logError("createPPTextField: " + e.message);
         }
      }

      private function applyAutoSize(tf:TextField, align:String):void
      {
         if (align == "right") tf.autoSize = TextFieldAutoSize.RIGHT;
         else if (align == "center") tf.autoSize = TextFieldAutoSize.CENTER;
         else tf.autoSize = TextFieldAutoSize.LEFT;
      }

      private function updatePPTextFieldPosition(containerName:String, vehicleID:int, tf:TextField, container:Object):void
      {
         try
         {
            var listItem:* = this.getPPListItem(vehicleID);
            if (!listItem) return;
            var isEnemy:Boolean = this.isPPEnemy(vehicleID);
            var posConfig:Object = container[isEnemy ? "right" : "left"];
            var holderName:String = container["holder"];

            var baseX:Number = 0;
            var baseY:Number = 0;
            if (holderName && listItem.hasOwnProperty(holderName))
            {
               var holder:DisplayObject = listItem[holderName] as DisplayObject;
               if (holder)
               {
                  baseX = holder.x;
                  baseY = holder.y;
               }
            }

            var offsetX:Number = posConfig.x || 0;
            var offsetY:Number = posConfig.y || 0;

            var state:int = -1;
            if (listItem.hasOwnProperty("state"))
            {
               state = int(listItem.state);
            }

            if (posConfig.hasOwnProperty("stateOffsets") && state >= 0)
            {
               var stateKey:String = "state" + String(state);
               var stateOffsets:Object = posConfig.stateOffsets;
               if (stateOffsets && stateOffsets.hasOwnProperty(stateKey))
               {
                  var stateOffset:Object = stateOffsets[stateKey];
                  if (stateOffset.hasOwnProperty("x")) offsetX = stateOffset.x;
                  if (stateOffset.hasOwnProperty("y")) offsetY = stateOffset.y;
               }
            }

            tf.x = baseX + offsetX;
            tf.y = baseY + offsetY;

            var shouldHide:Boolean = false;
            if (state == PLAYERS_PANEL_STATE.HIDDEN)
            {
               shouldHide = true;
            }
            else if (posConfig.hasOwnProperty("hideInStates"))
            {
               var hideStates:Array = posConfig.hideInStates as Array;
               if (hideStates)
               {
                  for each (var hideState:int in hideStates)
                  {
                     if (hideState == state)
                     {
                        shouldHide = true;
                        break;
                     }
                  }
               }
            }

            if (shouldHide) tf.visible = false;
         }
         catch (e:Error)
         {
            this.logError("updatePPTextFieldPosition: " + e.message);
         }
      }

      /**
       *  Tab-menu overlay: Python passes two arrays of { vehicleID, text } in
       *  the exact row order used by WG in FullStatsTable.playerNameCollection.
       *  We anchor our own TextField next to each playerName_cXrY — WG's
       *  original TextField is untouched.
       */
      public function as_setTabOverlay(allies:Array, enemies:Array):void
      {
         if (this._isDisposed) return;
         try
         {
            var table:FullStatsTableBase = this.getFullStatsTable();
            if (table == null || table.playerNameCollection == null) return;

            this.applyTabOverlayRow(table, allies, false);
            this.applyTabOverlayRow(table, enemies, true);
         }
         catch (e:Error)
         {
            this.logError("as_setTabOverlay: " + e.message);
         }
      }

      public function as_clearTabOverlay():void
      {
         if (this._isDisposed || this._tabOverlayTextFields == null) return;
         for (var i:int = 0; i < this._tabOverlayTextFields.length; i++)
         {
            var tf:TextField = this._tabOverlayTextFields[i];
            if (tf != null)
            {
               this.returnTextFieldToPool(tf);
               this._tabOverlayTextFields[i] = null;
            }
         }
      }

      private function getFullStatsTable():FullStatsTableBase
      {
         try
         {
            var page:BattlePage = this.battlePage as BattlePage;
            if (page == null) return null;
            var fullStats:* = page.fullStats;
            if (fullStats == null) return null;
            if (fullStats.hasOwnProperty("table"))
            {
               return fullStats["table"] as FullStatsTableBase;
            }
         }
         catch (e:Error)
         {
            this.logError("getFullStatsTable: " + e.message);
         }
         return null;
      }

      private function applyTabOverlayRow(table:FullStatsTableBase, rows:Array, isEnemy:Boolean):void
      {
         if (rows == null) return;
         var nameCollection:Vector.<TextField> = table.playerNameCollection;
         if (nameCollection == null) return;

         var baseIdx:int = isEnemy ? TAB_NUM_ROWS : 0;
         var count:int = rows.length > TAB_NUM_ROWS ? TAB_NUM_ROWS : rows.length;

         for (var row:int = 0; row < count; row++)
         {
            var collIdx:int = baseIdx + row;
            if (collIdx >= nameCollection.length) break;
            var anchor:TextField = nameCollection[collIdx];
            if (anchor == null) continue;

            var rowData:Object = rows[row];
            if (rowData == null) continue;

            var text:String = rowData.hasOwnProperty("text") ? String(rowData.text) : "";
            this.placeTabOverlay(collIdx, anchor, text, isEnemy);
         }

         for (var blankRow:int = count; blankRow < TAB_NUM_ROWS; blankRow++)
         {
            var slot:int = baseIdx + blankRow;
            var old:TextField = this._tabOverlayTextFields[slot];
            if (old != null)
            {
               old.htmlText = "";
               old.visible = false;
            }
         }
      }

      private function placeTabOverlay(slot:int, anchor:TextField, text:String, isEnemy:Boolean):void
      {
         var tf:TextField = this._tabOverlayTextFields[slot];
         if (tf == null)
         {
            tf = this.getTextFieldFromPool();
            tf.autoSize = isEnemy ? TextFieldAutoSize.LEFT : TextFieldAutoSize.RIGHT;
            tf.width = 120;
            tf.height = 20;
            tf.mouseEnabled = false;
            tf.selectable = false;
            var parent:flash.display.DisplayObjectContainer = anchor.parent;
            if (parent != null) parent.addChild(tf);
            this._tabOverlayTextFields[slot] = tf;
         }

         if (text == null || text.length == 0)
         {
            tf.htmlText = "";
            tf.visible = false;
            return;
         }

         tf.htmlText = text;
         tf.visible = true;

         if (isEnemy)
         {
            tf.x = anchor.x + anchor.textWidth + TAB_OVERLAY_OFFSET_X;
         }
         else
         {
            tf.x = anchor.x - tf.textWidth - TAB_OVERLAY_OFFSET_X;
         }
         tf.y = anchor.y;
      }

      public function as_vehicleIconColor(vehicleID:int, colorStr:String):void
      {
         if (this._isDisposed) return;
         try
         {
            var listItem:* = this.getPPListItem(vehicleID);
            if (!listItem) return;
            if (!listItem.hasOwnProperty("vehicleIcon")) return;
            var vehicleIcon:BattleAtlasSprite = listItem.vehicleIcon as BattleAtlasSprite;
            if (!vehicleIcon) return;

            vehicleIcon["playerPanel"] = {"color": Utils.colorConvert(colorStr)};

            if (!vehicleIcon.hasEventListener(Event.RENDER))
            {
               vehicleIcon.addEventListener(Event.RENDER, this.onRenderHandle, false, 0, true);
               this._eventListeners.push(vehicleIcon);
            }
         }
         catch (e:Error)
         {
            this.logError("as_vehicleIconColor: " + e.message);
         }
      }

      private function onRenderHandle(event:Event):void
      {
         var sprite:BattleAtlasSprite = event.target as BattleAtlasSprite;
         if (!sprite) return;
         var data:Object = sprite["playerPanel"];
         if (!data) return;
         var cTransform:ColorTransform = sprite.transform.colorTransform;
         cTransform.color = uint(data["color"]);
         sprite.transform.colorTransform = cTransform;
      }

      public function as_shadowListItem(shadow:Object):DropShadowFilter
      {
         if (!shadow) return null;
         return Utils.getDropShadowFilter(
            shadow.distance, shadow.angle, shadow.color,
            shadow.alpha, shadow.size, shadow.strength
         );
      }

      public function extendedSetting(containerName:String, vehicleID:int):TextField
      {
         try
         {
            var vehicleFields:Dictionary = this._vehicleTextFields[containerName] as Dictionary;
            if (!vehicleFields) return null;
            if (!vehicleFields[vehicleID])
            {
               var container:Object = this._containers[containerName];
               if (!container) return null;
               this.createPPTextField(containerName, vehicleID, container);
            }
            return vehicleFields[vehicleID] as TextField;
         }
         catch (e:Error)
         {
            this.logError("extendedSetting: " + e.message);
         }
         return null;
      }

      override protected function onDispose():void
      {
         this._isDisposed = true;
         try
         {
            if (this._statsCacheMgr)
            {
               this._statsCacheMgr.removeEventListener(StatisticDataEvent.CYCLIC_STATS_RECEIVED, this.onStatsReceived);
               this._statsCacheMgr = null;
            }
            this.cleanupEventListeners();
            this.cleanupTextFields();
            this.cleanupTabOverlay();
            this.cleanupPool();

            this._containers = null;
            this._vehicleTextFields = null;
            this._cachedShadows = null;
            this._defaultTextFormat = null;

            super.onDispose();
         }
         catch (e:Error)
         {
            this.logError("onDispose: " + e.message);
         }
      }

      private function cleanupTabOverlay():void
      {
         if (this._tabOverlayTextFields == null) return;
         for (var i:int = 0; i < this._tabOverlayTextFields.length; i++)
         {
            var tf:TextField = this._tabOverlayTextFields[i];
            if (tf != null && tf.parent != null)
            {
               tf.parent.removeChild(tf);
            }
         }
         this._tabOverlayTextFields = null;
      }

      private function cleanupEventListeners():void
      {
         if (!this._eventListeners) return;
         var len:int = this._eventListeners.length;
         for (var i:int = 0; i < len; i++)
         {
            var sprite:BattleAtlasSprite = this._eventListeners[i];
            if (sprite && sprite.hasEventListener(Event.RENDER))
            {
               sprite.removeEventListener(Event.RENDER, this.onRenderHandle);
            }
         }
         this._eventListeners.length = 0;
         this._eventListeners = null;
      }

      private function cleanupTextFields():void
      {
         if (!this._vehicleTextFields) return;
         for (var containerName:String in this._vehicleTextFields)
         {
            var vehicleFields:Dictionary = this._vehicleTextFields[containerName] as Dictionary;
            if (vehicleFields)
            {
               for (var vehicleId:* in vehicleFields)
               {
                  var tf:TextField = vehicleFields[vehicleId] as TextField;
                  if (tf) this.returnTextFieldToPool(tf);
               }
            }
         }
      }

      private function cleanupPool():void
      {
         if (!this._textFieldPool) return;
         var len:int = this._textFieldPool.length;
         for (var i:int = 0; i < len; i++)
         {
            var tf:TextField = this._textFieldPool[i];
            if (tf)
            {
               tf.filters = null;
               if (tf.parent) tf.parent.removeChild(tf);
            }
         }
         this._textFieldPool.length = 0;
         this._textFieldPool = null;
      }

      private function logError(message:String):void
      {
         var fullMessage:String = "[playerPanel] " + message;
         if (this.flashLogS != null) this.flashLogS(fullMessage);
         trace(fullMessage);
      }
   }
}
