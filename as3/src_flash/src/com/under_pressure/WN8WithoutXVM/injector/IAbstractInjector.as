package com.under_pressure.WN8WithoutXVM.injector
{
   import flash.events.IEventDispatcher;

   public interface IAbstractInjector extends IEventDispatcher
   {
      function get componentName():String;
      function get componentUI():Class;
   }
}
