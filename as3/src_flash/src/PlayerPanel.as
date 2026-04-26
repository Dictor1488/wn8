package
{
   import com.under_pressure.WN8WithoutXVM.battle.playerPanel;
   import com.under_pressure.WN8WithoutXVM.injector.AbstractViewInjector;
   import com.under_pressure.WN8WithoutXVM.injector.IAbstractInjector;

   public class PlayerPanel extends AbstractViewInjector implements IAbstractInjector
   {
      public function PlayerPanel()
      {
         super();
      }

      override public function get componentUI():Class
      {
         return playerPanel;
      }

      override public function get componentName():String
      {
         return "playerPanel";
      }
   }
}
