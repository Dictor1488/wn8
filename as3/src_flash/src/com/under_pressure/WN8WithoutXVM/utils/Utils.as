package com.under_pressure.WN8WithoutXVM.utils
{
   import flash.filters.BitmapFilterQuality;
   import flash.filters.DropShadowFilter;

   public class Utils
   {
      public function Utils()
      {
         super();
      }

      public static function colorConvert(colorStr:String):uint
      {
         var result:uint = 0xFFFFFF;

         if (!colorStr || colorStr.length == 0)
         {
            return 0xFFFFFF;
         }

         try
         {
            var cleanColor:String = colorStr;

            if (cleanColor.charAt(0) == "#")
            {
               cleanColor = "0x" + cleanColor.substr(1);
            }
            else if (cleanColor.substr(0, 2) != "0x")
            {
               cleanColor = "0x" + cleanColor;
            }

            var parsedColor:uint = uint(parseInt(cleanColor, 16));

            if (!isNaN(parsedColor))
            {
               result = parsedColor;
            }
         }
         catch (e:Error)
         {
            result = 0xFFFFFF;
         }

         return result;
      }

      public static function getDropShadowFilter(
         distance:Number,
         angle:Number,
         color:String,
         alpha:Number,
         size:Number,
         strength:Number
      ):DropShadowFilter
      {
         var filter:DropShadowFilter;

         try
         {
            filter = new DropShadowFilter();
            filter.distance = isNaN(distance) ? 0 : distance;
            filter.angle = clamp(angle, 0, 360);
            filter.color = colorConvert(color);
            filter.alpha = clamp(0.01 * alpha, 0, 1);
            filter.blurX = clamp(size, 0, 255);
            filter.blurY = clamp(size, 0, 255);
            filter.strength = clamp(0.01 * strength, 0, 255);
            filter.quality = BitmapFilterQuality.MEDIUM;
            filter.inner = false;
            filter.knockout = false;
            filter.hideObject = false;
         }
         catch (e:Error)
         {
            filter = new DropShadowFilter(0, 90, 0x000000, 1.0, 2, 2, 1.0, BitmapFilterQuality.MEDIUM);
         }

         return filter;
      }

      public static function clamp(value:Number, min:Number, max:Number):Number
      {
         if (isNaN(value)) return min;
         if (isNaN(min)) min = 0;
         if (isNaN(max)) return value;
         return Math.max(min, Math.min(max, value));
      }

      public static function formatNumber(num:Number, decimals:int = 0):String
      {
         if (isNaN(num)) return "0";

         if (decimals <= 0)
         {
            return String(int(num));
         }

         var multiplier:Number = Math.pow(10, decimals);
         var rounded:Number = Math.round(num * multiplier) / multiplier;
         var result:String = String(rounded);

         var dotIndex:int = result.indexOf(".");
         if (dotIndex == -1)
         {
            result += ".";
            for (var i:int = 0; i < decimals; i++)
            {
               result += "0";
            }
         }
         else
         {
            var currentDecimals:int = result.length - dotIndex - 1;
            for (var j:int = currentDecimals; j < decimals; j++)
            {
               result += "0";
            }
         }

         return result;
      }

      public static function rgbToHex(r:uint, g:uint, b:uint):uint
      {
         return (r << 16) | (g << 8) | b;
      }

      public static function hexToRgb(hex:uint):Object
      {
         return {
            r: (hex >> 16) & 0xFF,
            g: (hex >> 8) & 0xFF,
            b: hex & 0xFF
         };
      }
   }
}
